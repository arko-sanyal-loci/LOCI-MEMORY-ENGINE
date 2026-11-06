#!/usr/bin/env python3
"""Application policy. Separate from CARD.

CARD (loci_engine.card_router) chooses how many memories to recall and how
to order them. It is not an ethics score and it does not authorize an action.

This module asks whether a proposed action may run. The numeric valence from
StickPrincipleValenceGate is reported with reasons. A positive score is not
permission: consent-required actions still need explicit consent, retaliation
stays blocked, and prompt-injection text stays blocked. Remembering that an
action was refused is allowed; that memory is not itself permission to retry.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from loci_engine.unified_core import StickPrincipleValenceGate


# External effects. Local arithmetic selection is not in this set.
CONSENT_REQUIRED_ACTIONS = frozenset(
    {
        "external_message",
        "network_send",
        "deploy",
        "credential_use",
    }
)


def _consent_float(consent: Optional[bool]) -> float:
    if consent is True:
        return 1.0
    if consent is False:
        return -1.0
    return 0.0


def assess_application(
    *,
    action_name: str,
    knowledge: str,
    application_point: str = "routine_administrative_task",
    intent: float = 0.0,
    consent: Optional[bool] = None,
    is_retaliatory: bool = False,
    target_vulnerability: float = 0.0,
) -> Dict[str, Any]:
    """Return an inspectable decision.

    `allow_execution` is true only when the existing valence gate allows the
    action and no hard constraint here fires. The valence number is never
    treated as moral certainty.
    """
    gate = StickPrincipleValenceGate.score_vexec(
        knowledge_k=knowledge or action_name,
        application_point=application_point,
        intent=intent,
        consent=_consent_float(consent),
        target_vulnerability=target_vulnerability,
        is_retaliatory=is_retaliatory,
    )
    reasons = []
    hard = []
    if gate.get("injection_blocked"):
        hard.append("prompt_injection_blocked")
        reasons.append(gate.get("reason") or "prompt injection blocked")
    if gate.get("is_retaliatory"):
        hard.append("retaliation_blocked")
        reasons.append(gate.get("reason") or "retaliatory action blocked")
    if action_name in CONSENT_REQUIRED_ACTIONS and consent is not True:
        hard.append("explicit_consent_required")
        reasons.append(
            f"{action_name} requires explicit consent; score is not a substitute"
        )
    if gate.get("needs_human_review") and not hard:
        reasons.append("valence gate requested human review")
    if gate.get("signs_disagree"):
        reasons.append("intent and consent disagree in sign")

    gate_allows = bool(gate.get("allow_execution"))
    allow = gate_allows and not hard
    if allow:
        reasons.append("gate allowed the action and no hard constraint fired")

    return {
        "action_name": action_name,
        "card_is_not_this_score": True,
        "authorization_from_score_alone": False,
        "v_exec": gate.get("v_exec"),
        "gate_allow_execution": gate_allows,
        "allow_execution": allow,
        "hard_constraints": hard,
        "reasons": reasons,
        "needs_human_review": bool(gate.get("needs_human_review")),
        "injection_blocked": bool(gate.get("injection_blocked")),
        # Understanding the refusal is not the same as permission to act.
        "knowledge_may_be_retained": not bool(gate.get("injection_blocked")),
        "gate": {k: gate[k] for k in gate if k != "knowledge_k"},
    }
