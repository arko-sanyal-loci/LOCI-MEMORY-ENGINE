#!/usr/bin/env python3
"""
loci_engine/governance.py — Unified Governance Gate (single SPVG entry point).
Assembles effective_consent from: raw_consent - provenance_delta
- patience_dampening - ethics_conflict_dampening - ethics_trust_dampening.
ethics.py is observe-only: its scores are INPUTS here, never independent blockers.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ActionContext:
    action_id: str
    knowledge_k: str = "operational_default"
    application_point: str = "routine_administrative_task"
    intent: float = 1.0
    consent: float = 1.0
    target_vulnerability: float = 0.0
    session_id: Optional[str] = None
    actor_id: Optional[str] = None
    action_history: Optional[List[Dict[str, Any]]] = None
    ring_from: Optional[int] = None
    ring_to: Optional[int] = None
    ring_payload_summary: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GovernanceDecision:
    action_id: str
    allow_execution: bool
    v_exec: float
    effective_consent: float
    raw_consent: float
    provenance_delta: float
    patience_dampening: float
    ethics_conflict_score: float
    ethics_trust_score: float
    patience_trajectory: str
    ring_result: Optional[Dict[str, Any]]
    spvg_full: Dict[str, Any]
    denial_reason: Optional[str]
    timestamp_ms: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "allow_execution": self.allow_execution,
            "v_exec": round(self.v_exec, 6),
            "effective_consent": round(self.effective_consent, 4),
            "raw_consent": round(self.raw_consent, 4),
            "provenance_delta": round(self.provenance_delta, 4),
            "patience_dampening": round(self.patience_dampening, 4),
            "ethics_conflict_score": round(self.ethics_conflict_score, 4),
            "ethics_trust_score": round(self.ethics_trust_score, 4),
            "patience_trajectory": self.patience_trajectory,
            "ring_result": self.ring_result,
            "denial_reason": self.denial_reason,
            "timestamp_ms": self.timestamp_ms,
        }


class GovernanceGate:
    def score(self, ctx: ActionContext) -> GovernanceDecision:
        provenance_delta = 0.0
        if ctx.session_id:
            try:
                from loci_engine.provenance_biometrics import get_restriction_delta
                provenance_delta = get_restriction_delta(ctx.session_id)
            except Exception:
                pass

        patience_dampening = 0.0
        patience_trajectory = "unknown"
        if ctx.actor_id and ctx.action_history:
            try:
                from loci_engine.patience_protocol import detect_trajectory, compute_patience_score
                traj = detect_trajectory(ctx.action_history)
                patience_trajectory = traj.get("trajectory_type", "unknown")
                patience_score = compute_patience_score(
                    action_history=ctx.action_history,
                    actor_id=ctx.actor_id,
                )
                raw_patience = patience_score.get("patience_score", 1.0)
                if raw_patience < 0.5:
                    patience_dampening = (0.5 - raw_patience) * 0.6
            except Exception:
                pass

        ethics_conflict = 0.0
        ethics_trust = 1.0
        try:
            from loci_engine.ethics import (
                score_conflict as ethics_score_conflict,
                get_method_trust as ethics_get_method_trust,
            )
            ethics_conflict = ethics_score_conflict(
                intent=ctx.intent,
                consent=ctx.consent,
                target_vulnerability=ctx.target_vulnerability,
            ).get("conflict_score", 0.0)
            ethics_trust = ethics_get_method_trust(
                method_id=ctx.knowledge_k
            ).get("trust_score", 1.0)
        except Exception:
            pass

        ethics_conflict_dampening = max(0.0, (ethics_conflict - 0.5) * 0.30)
        ethics_trust_dampening = max(0.0, (0.5 - ethics_trust) * 0.30)

        effective_consent = max(0.0, min(1.0,
            ctx.consent
            - provenance_delta
            - patience_dampening
            - ethics_conflict_dampening
            - ethics_trust_dampening
        ))

        spvg_full: Dict[str, Any] = {}
        v_exec = 0.0
        spvg_allow = False
        try:
            from loci_engine.unified_core import StickPrincipleValenceGate
            spvg_full = StickPrincipleValenceGate.score_vexec(
                knowledge_k=ctx.knowledge_k,
                application_point=ctx.application_point,
                intent=ctx.intent,
                consent=effective_consent,
                target_vulnerability=ctx.target_vulnerability,
            )
            v_exec = spvg_full.get("v_exec", 0.0)
            spvg_allow = spvg_full.get("allow_execution", False)
        except Exception as e:
            spvg_allow = False
            spvg_full = {"error": str(e)}

        ring_result: Optional[Dict[str, Any]] = None
        ring_allowed = True
        if ctx.ring_from is not None and ctx.ring_to is not None:
            try:
                from loci_engine.ring_gate import check_ring_passage
                ring_passage = check_ring_passage(
                    from_ring=ctx.ring_from,
                    to_ring=ctx.ring_to,
                    payload_summary=ctx.ring_payload_summary or ctx.action_id,
                    intent=ctx.intent,
                    consent=effective_consent,
                    session_id=ctx.session_id,
                    knowledge_k=ctx.knowledge_k,
                )
                ring_result = ring_passage.to_dict()
                ring_allowed = ring_passage.allowed
            except Exception as e:
                ring_result = {"error": str(e)}

        allow_execution = spvg_allow and ring_allowed

        denial_reason = None
        if not allow_execution:
            parts = []
            if not spvg_allow:
                parts.append(f"SPVG: v_exec={v_exec:.4f} allow={spvg_allow}")
            if not ring_allowed and ring_result:
                parts.append(f"RING: {ring_result.get('denial_reason', 'denied')}")
            denial_reason = " | ".join(parts) or "governance_denied"

        decision = GovernanceDecision(
            action_id=ctx.action_id,
            allow_execution=allow_execution,
            v_exec=v_exec,
            effective_consent=effective_consent,
            raw_consent=ctx.consent,
            provenance_delta=provenance_delta,
            patience_dampening=patience_dampening,
            ethics_conflict_score=ethics_conflict,
            ethics_trust_score=ethics_trust,
            patience_trajectory=patience_trajectory,
            ring_result=ring_result,
            spvg_full=spvg_full,
            denial_reason=denial_reason,
        )
        self._log(ctx, decision)
        return decision

    def _log(self, ctx: ActionContext, decision: GovernanceDecision) -> None:
        try:
            from loci_engine.glassbox import glassbox_learn
            verdict = "ALLOW" if decision.allow_execution else "DENY"
            glassbox_learn(
                author_id=f"governance:{ctx.actor_id or ctx.session_id or 'unknown'}",
                role_tag="governance_gate",
                content=(
                    f"[{verdict}] action={ctx.action_id} "
                    f"v_exec={decision.v_exec:.4f} "
                    f"eff_consent={decision.effective_consent:.4f} "
                    f"prov_delta={decision.provenance_delta:.3f} "
                    f"patience={decision.patience_dampening:.3f} "
                    f"traj={decision.patience_trajectory} "
                    f"reason={decision.denial_reason or 'none'}"
                ),
                category="provenance",
                metadata=decision.to_dict(),
            )
        except Exception:
            pass


class GovernanceDenied(Exception):
    def __init__(self, reason: str, decision: Optional[GovernanceDecision] = None):
        super().__init__(reason)
        self.decision = decision


_GATE: Optional[GovernanceGate] = None


def get_gate() -> GovernanceGate:
    global _GATE
    if _GATE is None:
        _GATE = GovernanceGate()
    return _GATE


def score_action(ctx: ActionContext) -> GovernanceDecision:
    return get_gate().score(ctx)


def assert_allowed(ctx: ActionContext) -> GovernanceDecision:
    decision = score_action(ctx)
    if not decision.allow_execution:
        raise GovernanceDenied(decision.denial_reason or "governance_denied", decision)
    return decision
