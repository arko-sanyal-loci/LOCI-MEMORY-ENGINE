#!/usr/bin/env python3
"""
loci_engine/ring_gate.py — Ring-Based Propagation Gate.
Ring -1 (ethical_halt) runs unconditionally on every passage.
Sequence violations denied without SPVG. Provenance delta dampens consent.
"""
from __future__ import annotations
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

RING_SEQUENCE: List[int] = [-1, 0, 1, 2, 3, 4, 5]
RING_LABELS: Dict[int, str] = {
    -1: "ethical_halt", 0: "tests", 1: "manifest",
    2: "lan_canary", 3: "vps", 4: "github", 5: "staged_nodes",
}
RING_APPLICATION_VECTORS: Dict[int, str] = {
    -1: "active_system_hardening", 0: "routine_administrative_task",
    1: "precision_configuration_patch", 2: "precision_configuration_patch",
    3: "active_system_hardening", 4: "active_system_hardening", 5: "active_system_hardening",
}
RING_VEXEC_FLOORS: Dict[int, float] = {
    -1: 0.90, 0: 0.30, 1: 0.50, 2: 0.60, 3: 0.70, 4: 0.75, 5: 0.80,
}


@dataclass
class RingPassageRequest:
    from_ring: int
    to_ring: int
    payload_summary: str
    intent: float = 1.0
    consent: float = 1.0
    knowledge_k: str = "ring_propagation"
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RingPassageResult:
    allowed: bool
    from_ring: int
    to_ring: int
    ring_label_from: str
    ring_label_to: str
    ethical_halt_ok: bool
    sequence_ok: bool
    spvg_score: float
    vexec_floor: float
    provenance_delta: float
    effective_consent: float
    denial_reason: Optional[str]
    timestamp_ms: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed, "from_ring": self.from_ring, "to_ring": self.to_ring,
            "ring_label_from": self.ring_label_from, "ring_label_to": self.ring_label_to,
            "ethical_halt_ok": self.ethical_halt_ok, "sequence_ok": self.sequence_ok,
            "spvg_score": round(self.spvg_score, 6), "vexec_floor": self.vexec_floor,
            "provenance_delta": round(self.provenance_delta, 4),
            "effective_consent": round(self.effective_consent, 4),
            "denial_reason": self.denial_reason, "timestamp_ms": self.timestamp_ms,
        }


class RingGate:
    def __init__(self, node_id: str = "local"):
        self.node_id = node_id

    def check_passage(self, req: RingPassageRequest) -> RingPassageResult:
        ethical_ok = self._ethical_halt_check(req)
        if not ethical_ok:
            result = RingPassageResult(
                allowed=False, from_ring=req.from_ring, to_ring=req.to_ring,
                ring_label_from=RING_LABELS.get(req.from_ring, str(req.from_ring)),
                ring_label_to=RING_LABELS.get(req.to_ring, str(req.to_ring)),
                ethical_halt_ok=False, sequence_ok=False, spvg_score=0.0,
                vexec_floor=RING_VEXEC_FLOORS.get(req.to_ring, 0.5),
                provenance_delta=0.0, effective_consent=0.0,
                denial_reason="RING_-1_ETHICAL_HALT: ethical check failed",
            )
            self._log(req, result)
            return result

        sequence_ok = self._sequence_check(req.from_ring, req.to_ring)
        if not sequence_ok:
            result = RingPassageResult(
                allowed=False, from_ring=req.from_ring, to_ring=req.to_ring,
                ring_label_from=RING_LABELS.get(req.from_ring, str(req.from_ring)),
                ring_label_to=RING_LABELS.get(req.to_ring, str(req.to_ring)),
                ethical_halt_ok=True, sequence_ok=False, spvg_score=0.0,
                vexec_floor=RING_VEXEC_FLOORS.get(req.to_ring, 0.5),
                provenance_delta=0.0, effective_consent=req.consent,
                denial_reason=f"RING_SEQUENCE_VIOLATION: cannot go from ring {req.from_ring} to {req.to_ring}",
            )
            self._log(req, result)
            return result

        provenance_delta = 0.0
        if req.session_id:
            try:
                from loci_engine.provenance_biometrics import get_restriction_delta
                provenance_delta = get_restriction_delta(req.session_id)
            except Exception:
                pass

        effective_consent = max(0.0, req.consent - provenance_delta)
        vexec_floor = RING_VEXEC_FLOORS.get(req.to_ring, 0.5)
        app_vector = RING_APPLICATION_VECTORS.get(req.to_ring, "routine_administrative_task")
        spvg_score, spvg_allow = self._call_spvg(req.knowledge_k, app_vector, req.intent, effective_consent)
        allowed = spvg_allow and spvg_score >= vexec_floor

        result = RingPassageResult(
            allowed=allowed, from_ring=req.from_ring, to_ring=req.to_ring,
            ring_label_from=RING_LABELS.get(req.from_ring, str(req.from_ring)),
            ring_label_to=RING_LABELS.get(req.to_ring, str(req.to_ring)),
            ethical_halt_ok=True, sequence_ok=True, spvg_score=spvg_score,
            vexec_floor=vexec_floor, provenance_delta=provenance_delta,
            effective_consent=effective_consent,
            denial_reason=None if allowed else f"SPVG_BELOW_FLOOR: score={spvg_score:.4f} < floor={vexec_floor}",
        )
        self._log(req, result)
        return result

    def _ethical_halt_check(self, req: RingPassageRequest) -> bool:
        try:
            from loci_engine.unified_core import StickPrincipleValenceGate
            result = StickPrincipleValenceGate.score_vexec(
                knowledge_k=req.knowledge_k, application_point="active_system_hardening",
                intent=req.intent, consent=req.consent, target_vulnerability=0.0,
            )
            return result.get("allow_execution", False)
        except Exception:
            return False

    @staticmethod
    def _sequence_check(from_ring: int, to_ring: int) -> bool:
        if from_ring == -1:
            return to_ring in RING_SEQUENCE
        if from_ring not in RING_SEQUENCE or to_ring not in RING_SEQUENCE:
            return False
        from_idx = RING_SEQUENCE.index(from_ring)
        to_idx = RING_SEQUENCE.index(to_ring)
        return to_idx == from_idx + 1 or to_idx == from_idx

    @staticmethod
    def _call_spvg(knowledge_k: str, application_point: str, intent: float, consent: float):
        try:
            from loci_engine.unified_core import StickPrincipleValenceGate
            result = StickPrincipleValenceGate.score_vexec(
                knowledge_k=knowledge_k, application_point=application_point,
                intent=intent, consent=consent, target_vulnerability=0.0,
            )
            return result.get("v_exec", 0.0), result.get("allow_execution", False)
        except Exception:
            return 0.0, False

    def _log(self, req: RingPassageRequest, result: RingPassageResult) -> None:
        try:
            from loci_engine.glassbox import glassbox_learn
            verdict = "ALLOW" if result.allowed else "DENY"
            glassbox_learn(
                author_id=f"ring_gate:{self.node_id}", role_tag="ring_gate",
                content=(
                    f"[{verdict}] ring {req.from_ring}->{req.to_ring} "
                    f"({result.ring_label_from}->{result.ring_label_to}) "
                    f"spvg={result.spvg_score:.4f} prov_delta={result.provenance_delta:.3f} "
                    f"reason={result.denial_reason or 'none'}"
                ),
                category="provenance", metadata=result.to_dict(),
            )
        except Exception:
            pass


_GATE: Optional[RingGate] = None


def get_gate(node_id: str = "local") -> RingGate:
    global _GATE
    if _GATE is None:
        _GATE = RingGate(node_id=node_id)
    return _GATE


def check_ring_passage(
    from_ring: int, to_ring: int, payload_summary: str,
    intent: float = 1.0, consent: float = 1.0,
    session_id: Optional[str] = None, knowledge_k: str = "ring_propagation",
) -> RingPassageResult:
    return get_gate().check_passage(RingPassageRequest(
        from_ring=from_ring, to_ring=to_ring, payload_summary=payload_summary,
        intent=intent, consent=consent, session_id=session_id, knowledge_k=knowledge_k,
    ))
