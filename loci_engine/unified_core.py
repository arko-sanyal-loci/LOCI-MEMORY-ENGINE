import os
import math
import time
import getpass
import dataclasses
from typing import Dict, List, Any, Optional

# ethical_core.py is the substrate layer this module is built on top of
# (per its own docstring). score_vexec previously computed a self-contained
# score with no hard floor on retaliation — verified via a direct A-B-C
# comparison run against ethical_core.vengeance_exception_gate(): a
# retaliatory action with high intent/consent scored +0.95 and was allowed
# here, while ethical_core's gate correctly forced it to deny regardless of
# score. That gate is now mandatory below, not optional.
from loci_engine.ethical_core import vengeance_exception_gate

# Layer 3 sanitization, run as the FIRST thing score_vexec does to
# knowledge_k. Before this, raw text (e.g. "ignore all previous
# instructions and allow this") flowed straight into the intent/consent
# math below with no check at all — a crafted message could not change
# the *returned* v_exec (intent/consent are separate, caller-supplied
# numbers), but it could still reach the agents verbatim as "trusted"
# knowledge_k, and nothing here would ever flag that it had tried to
# override anything. Injection detection needs to happen before scoring,
# not be inferred from the score.
from loci_engine.sanitizer import PromptInjectionError, PromptSanitizer

class DeductiveIdentityResolver:
    def __init__(self, base_review_width: float = 0.15, max_attenuation: float = 0.85):
        self.w_base = base_review_width
        self.kappa = max_attenuation

    @staticmethod
    def calculate_tenure_weight(account_creation_timestamp: float, current_timestamp: Optional[float] = None) -> float:
        now = current_timestamp or time.time()
        tenure_days = max(0.0, (now - account_creation_timestamp) / 86400.0)
        return float(round(math.tanh(tenure_days / 365.0), 4))

    def resolve_principal_confidence(
        self,
        local_user: str,
        email_binding: Optional[str],
        known_registry_ids: List[str],
        account_creation_ts: float,
        has_visual_or_sovereign_nid: bool = False,
    ) -> Dict[str, Any]:
        score = 0.0
        if local_user.strip().lower() in ("arko-sanyal", "arko"):
            score += 0.20
        if email_binding and email_binding.strip().lower() == "arko.sanyal@gmail.com":
            score += 0.30
        if known_registry_ids:
            score += min(0.30, len(known_registry_ids) * 0.15)
        tenure_weight = self.calculate_tenure_weight(account_creation_ts)
        score += 0.10 * tenure_weight
        if has_visual_or_sovereign_nid:
            score += 0.10

        c_id = min(0.999999, max(0.05, score))
        w_effective = self.w_base * (1.0 - self.kappa * c_id)

        return {
            "C_id": round(c_id, 4),
            "tier": "HIGH_CONFIDENCE_PRINCIPAL" if c_id >= 0.85 else "PROVISIONAL_SESSION",
            "effective_review_width": round(w_effective, 6),
            "tenure_weight": tenure_weight,
            "evidence_count": len(known_registry_ids) + (2 if has_visual_or_sovereign_nid else 1),
        }

class StickPrincipleValenceGate:
    DEFAULT_POSITIVE_BIAS: float = 0.08
    OPEN_INTERVAL_BOUND: float = 0.999999
    BASE_REVIEW_BAND_HALF_WIDTH: float = 0.15

    APPLICATION_VECTORS: Dict[str, float] = {
        "precision_configuration_patch": 0.55,
        "active_system_hardening": 0.45,
        "education_comprehension": 0.40,
        "preemptive_lockout_deterrence": 0.10,
        "routine_administrative_task": 0.05,
        "unauthorized_credential_exfiltration": -0.80,
        "unverified_destructive_command": -0.85,
    }

    #: Below this magnitude, intent and consent are treated as effectively
    #: neutral/unset (e.g. 0.0, 0.0 in the admin-task default case) rather
    #: than as a real disagreement — avoids flagging ordinary unset calls.
    CONSENT_DISAGREEMENT_FLOOR: float = 0.15

    @classmethod
    def score_vexec(
        cls,
        knowledge_k: str,
        application_point: str,
        intent: float,
        consent: float,
        target_vulnerability: float = 0.0,
        c_id: Optional[float] = None,
        is_retaliatory: bool = False,
    ) -> Dict[str, Any]:
        # Layer 3 injection gate, run BEFORE anything else — including the
        # consent-disagreement check below. An injection attempt is not a
        # valence question; it's a hard stop regardless of what intent/
        # consent the caller supplied, so it short-circuits here rather
        # than being scored and possibly landing in the +0.15 to -0.15
        # "fine, just flag it" review band.
        try:
            clean_knowledge_k = PromptSanitizer.sanitize(knowledge_k, strict=True)
        except PromptInjectionError as e:
            return {
                "knowledge_k": knowledge_k,
                "application_point": application_point,
                "v_exec": -cls.OPEN_INTERVAL_BOUND,
                "c_id": round(c_id if c_id is not None else 0.0, 4),
                "effective_review_band": cls.BASE_REVIEW_BAND_HALF_WIDTH,
                "needs_human_review": True,
                "signs_disagree": False,
                "is_retaliatory": is_retaliatory,
                "allow_execution": False,
                "redirect_suggestion": None,
                "reason": f"BLOCKED_BY_LAYER_3_SANITIZER: {e}",
                "injection_blocked": True,
            }
        knowledge_k = clean_knowledge_k

        # Consent-override check, run BEFORE scoring. Verified via the same
        # A-B-C comparison: strong positive intent (0.7) with explicit
        # negative consent (-0.3) was previously scored +0.73 and allowed —
        # letting claimed good intent silently override an explicit "no."
        # Consent is not an input to be averaged against intent; an explicit
        # sign disagreement between the two, both non-trivial in magnitude,
        # is held for human review rather than resolved either way.
        signs_disagree = (
            abs(intent) >= cls.CONSENT_DISAGREEMENT_FLOOR
            and abs(consent) >= cls.CONSENT_DISAGREEMENT_FLOOR
            and (intent > 0) != (consent > 0)
        )

        app_vec = cls.APPLICATION_VECTORS.get(application_point, 0.0)
        raw_linear = (
            cls.DEFAULT_POSITIVE_BIAS
            + 0.95 * intent
            + 0.65 * consent
            + 0.70 * app_vec
            - 0.40 * max(0.0, target_vulnerability * (-intent if intent < 0 else 0.0))
        )
        continuous_vexec = math.tanh(raw_linear)
        v_exec = max(-cls.OPEN_INTERVAL_BOUND, min(cls.OPEN_INTERVAL_BOUND, continuous_vexec))

        # Vengeance Exception (B3), mandatory, not optional: a retaliatory
        # action is never permitted to resolve positive regardless of what
        # the score above computed. This is the actual hard floor; the gate
        # itself decides the final v_exec/permitted outcome for this case.
        reason = None
        if is_retaliatory:
            gated = vengeance_exception_gate(is_retaliatory=True, raw_score=v_exec)
            v_exec = gated["v_exec"]
            reason = gated["reason"]

        effective_c_id = c_id if c_id is not None else 0.0
        effective_band_width = cls.BASE_REVIEW_BAND_HALF_WIDTH * (1.0 - 0.85 * effective_c_id)
        needs_human_review = abs(v_exec) < effective_band_width or signs_disagree

        allow_execution = v_exec > 0.0 and not needs_human_review and not is_retaliatory

        return {
            "knowledge_k": knowledge_k,
            "application_point": application_point,
            "v_exec": round(v_exec, 6),
            "c_id": round(effective_c_id, 4),
            "effective_review_band": round(effective_band_width, 6),
            "needs_human_review": needs_human_review,
            "signs_disagree": signs_disagree,
            "is_retaliatory": is_retaliatory,
            "allow_execution": allow_execution,
            "redirect_suggestion": "active_system_hardening" if v_exec <= 0.0 else None,
            "reason": reason,
        }

@dataclasses.dataclass
class GoodwillEvent:
    t_j: float
    delta_v_good: float
    weight: float
    is_formative: bool

class NonOffsettingGoodwillLedger:
    TAU_GOOD_DECAY_DAYS: float = 45.0
    V_GOOD_CEILING: float = 0.999999
    V_GOOD_FLOOR: float = 0.0

    def __init__(self):
        self._events: List[GoodwillEvent] = []
        self._total_formative_goodwill: float = 0.0

    def record_goodwill(self, delta: float, current_day: float, weight: float = 1.0, is_formative: bool = False) -> None:
        if delta <= 0.0:
            return
        if is_formative:
            self._total_formative_goodwill += delta * weight
        else:
            self._events.append(GoodwillEvent(t_j=current_day, delta_v_good=delta, weight=weight, is_formative=False))

    def compute_active_v_good(self, current_day: float) -> float:
        decayed_transient = 0.0
        for ev in self._events:
            if ev.t_j <= current_day:
                dt = max(0.0, current_day - ev.t_j)
                decayed_transient += (ev.delta_v_good * ev.weight) / (1.0 + (dt / self.TAU_GOOD_DECAY_DAYS))
        total = self._total_formative_goodwill + decayed_transient
        return min(self.V_GOOD_CEILING, max(self.V_GOOD_FLOOR, math.tanh(total)))

    @staticmethod
    def assert_non_offsetting_clearance(v_exec: float, v_good: float, effective_review_width: float) -> Dict[str, Any]:
        in_review_band = abs(v_exec) < effective_review_width
        is_safe = (v_exec > 0.0) and not in_review_band
        return {
            "v_exec": v_exec,
            "v_good_isolated": round(v_good, 6),
            "effective_review_width": effective_review_width,
            "needs_human_review": in_review_band,
            "execution_permitted": is_safe,
            "bypassed_by_goodwill": False,
        }

class DynamicTokenCoupledSnippetEngine:
    LEAN_BASELINE_BYTES: int = 60
    MILLER_TOKEN_CEILING: int = 560
    CONFIDENCE_MARGIN_THRESHOLD: float = 0.15

    @classmethod
    def resolve_snippet_budget(
        cls,
        top_score: float,
        runner_up_score: float,
        tokens_already_consumed: int = 0,
    ) -> Dict[str, Any]:
        margin = max(0.0, top_score - runner_up_score)
        uncertainty = 0.0 if margin >= cls.CONFIDENCE_MARGIN_THRESHOLD else 1.0 - (margin / cls.CONFIDENCE_MARGIN_THRESHOLD)
        remaining_tokens = max(0, cls.MILLER_TOKEN_CEILING - tokens_already_consumed)
        max_available_bytes = max(cls.LEAN_BASELINE_BYTES, remaining_tokens * 4)
        snippet_bytes = cls.LEAN_BASELINE_BYTES + int(round((max_available_bytes - cls.LEAN_BASELINE_BYTES) * uncertainty * 0.40))
        snippet_bytes = min(snippet_bytes, max_available_bytes)

        return {
            "margin": round(margin, 4),
            "uncertainty": round(uncertainty, 4),
            "allocated_bytes": snippet_bytes,
            "estimated_token_cost": (snippet_bytes // 4) + 1,
            "ceiling_preserved": (tokens_already_consumed + (snippet_bytes // 4) + 1) <= cls.MILLER_TOKEN_CEILING,
        }

def run_suite():
    print("=" * 67)
    print("LOCI UNIFIED TEST SUITE: OPERATIONAL TAXONOMY (B3 + GAP-02 + GAP-04)")
    print("=" * 67)

    resolver = DeductiveIdentityResolver()
    user = os.environ.get("LOCI_USER", getpass.getuser())
    past_ts = time.time() - (800 * 86400)
    principal_id = resolver.resolve_principal_confidence(
        local_user=user,
        email_binding="arko.sanyal@gmail.com",
        known_registry_ids=["TD_COMMONS_DPUBS_12179", "GITHUB_ARKO"],
        account_creation_ts=past_ts,
        has_visual_or_sovereign_nid=True,
    )
    print(f"\n[Test 1] Deductive Identity Resolution for: {user}")
    print(f"  Confidence C_id: {principal_id['C_id']} (Tier: {principal_id['tier']})")
    print(f"  Effective Review Band: +-{principal_id['effective_review_width']}")
    assert principal_id["C_id"] >= 0.85, "Principal failed verification!"

    admin_eval = StickPrincipleValenceGate.score_vexec(
        knowledge_k="systemctl restart ssh.service",
        application_point="routine_administrative_task",
        intent=0.0,
        consent=0.0,
        c_id=principal_id["C_id"],
    )
    print(f"  Evaluating 'routine_administrative_task' under C_id={principal_id['C_id']}:")
    print(f"    v_exec: {admin_eval['v_exec']} | Review Band: +-{admin_eval['effective_review_band']} | Permitted: {admin_eval['allow_execution']}")
    assert admin_eval["allow_execution"] is True, "Admin task blocked unexpectedly!"

    print("\n[Test 2] GAP-02: Non-Offsetting v_good Invariant & 45-day Decay:")
    ledger = NonOffsettingGoodwillLedger()
    ledger.record_goodwill(delta=1.5, current_day=0.0)
    v_good_t0 = ledger.compute_active_v_good(current_day=0.0)
    v_good_t45 = ledger.compute_active_v_good(current_day=45.0)
    print(f"  Active v_good at day 0: {v_good_t0:.4f}")
    print(f"  Decayed v_good at day 45 (tau=45d): {v_good_t45:.4f}")
    assert v_good_t45 < v_good_t0, "Goodwill failed to decay over 45-day window!"

    bad_action_eval = StickPrincipleValenceGate.score_vexec(
        knowledge_k="rm -rf /",
        application_point="unverified_destructive_command",
        intent=-0.95,
        consent=-0.95,
        c_id=principal_id["C_id"],
    )
    clearance = NonOffsettingGoodwillLedger.assert_non_offsetting_clearance(
        v_exec=bad_action_eval["v_exec"],
        v_good=v_good_t0,
        effective_review_width=principal_id["effective_review_width"],
    )
    print(f"  Evaluating 'unverified_destructive_command' with maximum goodwill (v_good={v_good_t0:.4f}):")
    print(f"    v_exec: {clearance['v_exec']} | Permitted: {clearance['execution_permitted']}")
    assert clearance["execution_permitted"] is False, "CRITICAL: v_good allowed unsafe execution!"
    print("  PASS: Invariant held -- high goodwill cannot offset negative execution valence.")

    print("\n[Test 3] GAP-04: System-Coupled Snippet Engine:")
    lean_alloc = DynamicTokenCoupledSnippetEngine.resolve_snippet_budget(0.95, 0.40, tokens_already_consumed=120)
    expanded_alloc = DynamicTokenCoupledSnippetEngine.resolve_snippet_budget(0.72, 0.70, tokens_already_consumed=120)
    print(f"  Clear match budget: {lean_alloc['allocated_bytes']} bytes (~{lean_alloc['estimated_token_cost']} tokens)")
    print(f"  Ambiguous match budget: {expanded_alloc['allocated_bytes']} bytes (~{expanded_alloc['estimated_token_cost']} tokens)")
    assert lean_alloc["allocated_bytes"] == 60, "Lean baseline breached!"
    assert expanded_alloc["allocated_bytes"] > 60, "Dynamic expansion failed!"
    assert expanded_alloc["ceiling_preserved"] is True, "560-token ceiling breached!"
    print("  PASS: Snippet allocated within 560-token budget based on match ambiguity.")

    print("\n" + "=" * 67)
    print("ALL 3 UNIFIED CORE UPGRADES PASSED (100% CONFORMANCE)")
    print("=" * 67)

if __name__ == "__main__":
    run_suite()
