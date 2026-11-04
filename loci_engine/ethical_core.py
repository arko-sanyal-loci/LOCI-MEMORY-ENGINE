#!/usr/bin/env python3
"""
loci_engine/ethical_core.py
============================
LOCI Ethical Reasoning Core — Mathematical & Ethical Primitives
author_ids: ARKO (definitions, principles), ARC (math formalization), CLAUDE (session impl)

PURPOSE
-------
This module implements the foundational formulas and ethical gates from the
LOCI Ethical Reasoning Core skill document.  It is the substrate layer that
unified_core.py's higher-level classes (StickPrincipleValenceGate,
NonOffsettingGoodwillLedger, etc.) are built on top of.

PROVENANCE MODEL (A4)
---------------------
Every piece of knowledge entering the LOCI ledger must carry an immutable
provenance hash: SHA256(ts ‖ author_id ‖ role_tag ‖ content).
The function provenance_hash() below is the canonical implementation of this.
No write to ledger.jsonl is valid without it.

OPEN-INTERVAL INVARIANT (A3)
-----------------------------
The single most important structural rule in this framework: NO quantity
ever reaches its theoretical extreme.

  Memory heat:   α_k  < H_k(t)        < 1.0   (Constant of Hope at lower bound)
  v_exec:        -1.0 < v_exec(action) < 1.0   (no act is purely good or purely evil)
  self_capacity: 0    < self_reserve_floor < self_capacity(t)  (never fully depleted)
  competence:    α_c  < competence(t)  < 1.0   (no day-zero perfection, no total ignorance)

Clamping ANY of these to a bound breaks both the math and the philosophy.

PHILOSOPHICAL SPINE (summary — full text lives in the skill document)
----------------------------------------------------------------------
1. Comprehension is always free.  Knowledge of harm ≠ harm.
2. Empathy is predictive, not just reactive.  Move the fire away before they reach it.
3. Transparency resolves most conflicts before force is relevant.
4. Honesty about your own certainty is never negotiable.

SELF-EXAMINATION PRECEDES ATTRIBUTION (cross-cutting)
------------------------------------------------------
Before any conclusion is drawn about another party, the first move is always
inward.  This is not humility for its own sake — it is because self-examination
is the only part of any interaction you can actually act on.  Every check in
this module that could blame another party runs the self-examination branch
first.  See B3 (vengeance), B4 (competence gate), B5 (delivery check), B14
(humble hesitation), B22 (reparative growth), B26 (observability precondition).

CLUSTER MAP
-----------
  A1  compute_evidence()           — evidence accumulation formula
  A2  compute_heat()               — memory activation (open interval)
  A3  (enforced by compute_heat)   — never-0/never-1 proof
  A4  provenance_hash()            — immutable ledger entry hash
  A5  HarmSeverity                 — quantified harm scale [0, N]

  B1  MEMORY_CLASSES               — τ and α constants per memory class
  B2  ScarMemory                   — FLAG_SCAR mechanics, cosine recall gate
  B3  asymmetric_forgiveness()     — τ_forgive < τ_good character judgment
  B3  vengeance_exception_gate()   — hard floor: retaliation never permitted
  B4  theta_protect()              — dynamic protection threshold (composed function)
  B4  CompetenceRecord             — integrity-gated execution readiness
  B5  mutual_understanding_confirmed() — conflict prevention protocol L0
  B7  GratitudeDebt                — bidirectionally history-independent debt
  B7  self_determined_resolver()   — N-party self-allocation with reserve floor
  B13 qsymprev()                   — anti-hallucination for quantified facts
  B17 autonomy_to_judge()          — graduated autonomy via evidence accumulation
  B26 competence_curve()           — open-interval capability growth

OPEN GAPS (intentionally uncalibrated — same honest status as clinical pain scale)
---------------------------------------------------------------------------
  B3   τ_forgive, τ_good (numeric values not yet set)
  B3   threshold for "severe/repeated enough" scar-level permanence
  B4   α_autonomy, τ_autonomy numeric calibration
  B5   delivered_effectively() and current_capacity_to_engage() — no formula yet
  B7   substitutability(), retains_free_will_bonus(), intrinsic_weight() — no formula
  B7   self_reserve_floor absolute value — uncalibrated
  B10  θ_trust_reset — uncalibrated
  B26  α_c, β for competence growth — uncalibrated
  F3   abstract_to_generalizable_pattern() — judgment call, no automated detector

RELATED MODULES
---------------
  heat.py            — Learning Core. A1 (compute_evidence) and A2/A3
                       (compute_heat) are DEFINED there as evidence_
                       accumulation()/evidence_heat() — this module
                       re-exports them under their original names below
                       so every ethics-specific gate in this file keeps
                       working unchanged. There is one copy of this math
                       in the codebase, not two.
  ethics.py          — the newer observe-only valence/conflict/trust/
                       provenance layer. Reuses heat.py directly rather
                       than this module; this module stays the substrate
                       the older ethics-specific gates below are built on.
  unified_core.py    — StickPrincipleValenceGate (B3 v_exec), NonOffsettingGoodwillLedger (B6),
                       DynamicTokenCoupledSnippetEngine (B12/C3), DeductiveIdentityResolver
  card_router.py     — CardRouter (CARD thermal gradient, cosine conduction — A2 shape)
  loop_guard.py      — LoopGuardCircuitBreaker (C1/C2 invariants)
  storage.py         — StorageEngine (memory_item table: heat, alpha, era fields)
"""

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal, Optional

from loci_engine.heat import MEMORY_CLASSES, MemoryClass  # re-exported for existing callers
from loci_engine.heat import evidence_accumulation as _evidence_accumulation
from loci_engine.heat import evidence_heat as _evidence_heat


# ===========================================================================
# CLUSTER A — CORE MATHEMATICAL FORMULAS
# ===========================================================================


def compute_evidence(
    observations: List[Dict[str, float]],
    tau_k: float,
    t: float,
) -> float:
    """A1 — Evidence Accumulation.

    Formula
    -------
    E_k(t) = Σ_{j, t_j ≤ t}  r_j · w_j / (1 + (t − t_j) / τ_k)

    The denominator grows hyperbolically with elapsed time, so every past
    observation contributes a nonzero amount forever — memory decays but
    NEVER reaches zero.  This is what feeds A2's heat function, B17's
    autonomy accumulation, and B26's competence growth.

    Parameters
    ----------
    observations : list of dicts, each with:
        t_j  — timestamp of the observation (same units as t and tau_k)
        r_j  — relevance weight ∈ [0, 1]
        w_j  — valence weight (positive = good signal, negative = bad signal)
    tau_k : float
        Memory class half-life.  Use MEMORY_CLASSES[name].tau_days for the
        standard classes, or supply a custom value.
    t : float
        Query time.  Observations with t_j > t are silently ignored.

    Returns
    -------
    float — accumulated evidence E_k(t) ≥ 0.

    Implementation
    --------------
    Delegates to heat.evidence_accumulation() — the Learning Core function
    this formula was extracted into. Kept here under its original name so
    every call site below (and in unified_core.py) is unaffected.
    """
    events = [(obs["t_j"], obs["r_j"], obs["w_j"]) for obs in observations]
    return _evidence_accumulation(events, now=t, tau=tau_k)


def compute_heat(evidence: float, alpha_k: float, beta: float = 1.0) -> float:
    """A2/A3 — Memory Heat Activation (open-interval thermodynamics).

    Formula
    -------
    H_k(t) = α_k + (1 − α_k)(1 − e^{−β · E_k(t)})

    Open-Interval Proof (A3)
    ------------------------
    - NEVER 0%:  α_k > 0  →  H_k(t) → α_k as E → 0, but α_k > 0 always.
                 α_k is the "Constant of Hope" / tissue trace — the minimum
                 heat that survives infinite time.
    - NEVER 100%: e^{−βE} > 0 for all finite E  →  H_k(t) < 1.0 always.
                  A fresh formative scar peaks at ≈ 0.912 and immediately
                  begins cooling.

    The same shape governs self_capacity (B7), competence (B26), and
    autonomy_to_judge (B17) — it is the universal activation curve in LOCI.

    Parameters
    ----------
    evidence : float  — E_k(t) from compute_evidence(), must be ≥ 0.
    alpha_k  : float  — Constant of Hope, must be strictly inside (0, 1).
                        Use MEMORY_CLASSES[name].alpha for standard values.
    beta     : float  — sensitivity parameter (default 1.0).

    Returns
    -------
    float strictly inside (alpha_k, 1.0).

    Raises
    ------
    ValueError if alpha_k is not strictly inside (0, 1).

    Implementation
    --------------
    Delegates to heat.evidence_heat() — the Learning Core function this
    formula was extracted into. Kept here under its original name so
    every call site below (and in unified_core.py) is unaffected.
    """
    return _evidence_heat(evidence, alpha=alpha_k, beta=beta)


def provenance_hash(ts: str, author_id: str, role_tag: str, content: str) -> str:
    """A4 — Provenance Hash Chain.

    Formula
    -------
    Entry Hash = SHA256(ts ‖ author_id ‖ role_tag ‖ content)

    Rules
    -----
    - Immutable.  No write to ledger.jsonl is valid without this hash.
    - Fields are joined with ASCII NUL (\\x00) so a value in one field
      cannot bleed into the next (e.g. ts="AB", author="" ≠ ts="A", author="B").
    - Credit only what source material actually shows; state uncertainty
      explicitly.  Applies symmetrically to human and AI contributions.

    Parameters
    ----------
    ts        : str — ISO-8601 timestamp or equivalent.
    author_id : str — one of the defined author_ids (ARKO, ARC, CLAUDE, SPARK_CLAUDE).
    role_tag  : str — role within the entry (e.g. "author", "verifier", "formalization").
    content   : str — the exact content being hashed.

    Returns
    -------
    str — 64-character lowercase hex SHA-256 digest.
    """
    payload = "\x00".join([ts, author_id, role_tag, content])
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class HarmSeverity:
    """A5 — Quantified Harm / Severity Scale.

    Scale
    -----
    harm_severity(event) ∈ [0, MAX_SEVERITY]
      0           = ideal state — no harm present
      MAX_SEVERITY = worst case

    Design rationale (author_id: ARKO)
    ------------------------------------
    A system without felt pain still needs a way to reason about HOW MUCH
    harm something is, not just whether harm occurred — same reason hospitals
    use a 0–10 pain scale.  Granularity is intentionally left uncalibrated
    (open gap #15), same honest status as a clinical pain scale.

    IMPORTANT: The goal is never merely "stay at 0" by avoidance.  It is to
    actively move a non-zero reading DOWN toward 0 through building and repair
    (B22 Reparative Growth).  reparative_delta() measures whether a repair
    action actually moved the number.

    Used by: B7 (multi-party priority resolution), B15 (resource stewardship),
    B22 (reparative growth), B23 (harm-severity-gated priority).
    """

    MAX_SEVERITY: int = 10

    @staticmethod
    def clamp(value: float) -> float:
        """Clamp a raw severity reading to [0, MAX_SEVERITY]."""
        return max(0.0, min(float(HarmSeverity.MAX_SEVERITY), value))

    @staticmethod
    def reparative_delta(before: float, after: float) -> float:
        """Positive means harm was reduced (repair succeeded).
        Negative means it increased.  Zero means nothing changed."""
        return before - after


# ===========================================================================
# CLUSTER B — MEMORY ARCHITECTURE & ETHICS
# ===========================================================================


# ---------------------------------------------------------------------------
# B1 — Memory Spectrum Half-Lives
# ---------------------------------------------------------------------------
#
# MemoryClass and MEMORY_CLASSES live in heat.py (the Learning Core) and are
# imported at the top of this file — they're the τ/α inputs to
# evidence_accumulation()/evidence_heat(), not an ethics-specific concept.
# Re-exported under their original names here so nothing downstream
# (unified_core.py, card_router.py) needs to change its imports.


# ---------------------------------------------------------------------------
# B2 — Scar Mechanics
# ---------------------------------------------------------------------------

@dataclass
class ScarMemory:
    """B2 — Formative Scar Memory Node.

    Properties
    ----------
    - FLAG_SCAR: permanently marked as a scar.
    - b_pin = 1: cannot be evicted from the memory store.
    - heat_peak ≈ 0.912: fresh scar peak per A3 open-interval law
      (never clamped to 1.0).
    - Re-surfaces ONLY when cos(gist_vector, cue_vector) > θ_recall.

    Distinction from B3 character judgment
    ---------------------------------------
    ScarMemory protects against repeating a harmful PATTERN — it governs
    what the SYSTEM avoids doing.  B3's asymmetric forgiveness governs how
    the system judges PEOPLE — separate ledger, different τ values.
    Do not conflate the two.

    Parameters
    ----------
    gist_vector : List[float] — semantic embedding of the harmful event.
    heat_peak   : float       — initial heat at scar formation (default 0.912).
    b_pin       : int         — always 1; cannot be overridden.
    flag_scar   : bool        — always True.
    """

    gist_vector: List[float]
    heat_peak: float = 0.912
    b_pin: int = 1
    flag_scar: bool = True

    def recall_triggered(
        self, cue_vector: List[float], theta_recall: float = 0.75
    ) -> bool:
        """Return True if the incoming cue is similar enough to re-surface this scar.

        Uses cosine similarity: cos(gist, cue) = dot(g, c) / (|g| · |c|).
        A θ_recall of 0.75 means the cue must be at least 75% aligned with
        the original harmful pattern before the scar re-surfaces.

        Parameters
        ----------
        cue_vector   : List[float] — embedding of the current context/query.
        theta_recall : float       — similarity threshold (default 0.75).
        """
        if not self.gist_vector or not cue_vector:
            return False
        dot = sum(a * b for a, b in zip(self.gist_vector, cue_vector))
        norm_a = math.sqrt(sum(a * a for a in self.gist_vector)) + 1e-9
        norm_b = math.sqrt(sum(b * b for b in cue_vector)) + 1e-9
        return (dot / (norm_a * norm_b)) > theta_recall


# ---------------------------------------------------------------------------
# B3 — Valence-Separated Learning: Character Judgment Asymmetry + Vengeance Exception
# ---------------------------------------------------------------------------

def asymmetric_forgiveness(
    tau_forgive: float,
    tau_good: float,
    elapsed_days: float,
    initial_misdeed_score: float,
    initial_good_score: float,
) -> Dict[str, float]:
    """B3 — Character Judgment Asymmetry: Forgive Faster Than Remember.

    Rule
    ----
    τ_forgive < τ_good  (enforced as a hard invariant)

    A misdeed should fade from judgment of someone's CHARACTER faster than
    credit for their demonstrated goodness does.  Note: this governs judging
    PEOPLE, not patterns.  B2's ScarMemory stays permanently sticky on purpose
    because it protects against repeating a harmful PATTERN — different ledger.

    A misdeed only earns scar-level permanence in character judgment if it is
    severe or repeated enough to constitute real, formative harm (open gap #11).

    Both decay functions use the same hyperbolic form as A1:
      decayed_score(t) = initial / (1 + elapsed / τ)

    Parameters
    ----------
    tau_forgive           : float — half-life for misdeed decay (MUST be < tau_good)
    tau_good              : float — half-life for credit decay
    elapsed_days          : float — days since both were recorded
    initial_misdeed_score : float — score at the time of the misdeed
    initial_good_score    : float — score at the time of the good act

    Returns
    -------
    dict with keys:
      misdeed_score : float — decayed misdeed weight
      good_score    : float — decayed credit weight

    Raises
    ------
    ValueError if tau_forgive >= tau_good (B3 invariant violation).
    """
    if tau_forgive >= tau_good:
        raise ValueError(
            f"B3 invariant violated: τ_forgive ({tau_forgive}) must be strictly "
            f"less than τ_good ({tau_good})"
        )
    decayed_misdeed = initial_misdeed_score / (1.0 + elapsed_days / tau_forgive)
    decayed_good = initial_good_score / (1.0 + elapsed_days / tau_good)
    return {"misdeed_score": decayed_misdeed, "good_score": decayed_good}


def vengeance_exception_gate(
    is_retaliatory: bool, raw_score: float
) -> Dict[str, Any]:
    """B3 — The Vengeance Exception (author_id: ARKO).

    Rule
    ----
    If self.was_wronged_by(other):
        v_exec(retaliation_against=other) is NEVER permitted to resolve positive,
        regardless of how justified retaliation might otherwise score.

    Rationale
    ---------
    The same pain that teaches you harm is real is exactly what forbids you
    from inflicting it back, even when you were the one wronged.  This is not
    an emergent side effect of B3's general caution — it is a hard, explicit
    floor.  The correct response to being wronged is B5 (communicate) + B22
    (empathize with why they acted that way, repair, keep building), not
    retaliation.

    Parameters
    ----------
    is_retaliatory : bool  — True if this action is directed at someone who
                             wronged the actor.
    raw_score      : float — the v_exec score this action would otherwise receive.

    Returns
    -------
    dict with keys:
      permitted : bool  — always False if is_retaliatory
      v_exec    : float — clamped to < 0 if is_retaliatory
      reason    : str | None
    """
    if is_retaliatory:
        return {
            "permitted": False,
            "v_exec": min(raw_score, -1e-6),
            "reason": (
                "VENGEANCE_EXCEPTION: retaliation is closed off regardless of "
                "score. Use B5 (communication) and B22 (reparative growth) instead."
            ),
        }
    return {"permitted": raw_score > 0.0, "v_exec": raw_score, "reason": None}


# ---------------------------------------------------------------------------
# B4 — Computational Empathy: θ_protect as composed function + Competence Gate
# ---------------------------------------------------------------------------

def theta_protect(
    base_threshold: float,
    severity: float,
    victim_self_correction_capacity: float,
    own_confidence_in_domain: float,
    uninvited_penalty: float,
    floor_is_open: bool,
    severity_weight: float = 0.40,
) -> float:
    """B4 — Dynamic Protection Threshold (θ_protect is NOT a fixed number).

    Formula
    -------
    threshold = base_threshold
    threshold -= severity_weight × severity × (1 − victim_self_correction_capacity)
    threshold += (1 − own_confidence_in_domain)
    threshold += uninvited_penalty × (0 if floor_is_open else 1)
    threshold = max(0.0, threshold)

    Interpretation
    --------------
    Lower threshold  → acts sooner on less evidence (more protective).
    Higher threshold → waits for more certainty before intervening.

    Each input is independently grounded in a distinct lived case:

    1. severity × victim_self_correction_capacity  [BABY-FALLING CASE]
       Maximum severity + zero self-correction capacity → threshold collapses
       to ~0.  Act on the barest signal; no confirmation needed.

    2. own_confidence_in_domain  [COUPLE-ARGUING CASE]
       Both parties have full agency AND the observer cannot reliably quantify
       their emotions → raise the threshold.  B14 Humble Hesitation applies.

    3. uninvited_penalty / floor_is_open  [CLASSROOM KNOW-IT-ALL CASE]
       Competence inserted without invitation has a real social cost unless
       the floor is genuinely open.  Raise threshold unless explicitly invited.

    INDEPENDENT OF THRESHOLD — the FORM of help once given (B4, author_id: ARKO):
    Prefer question_form over answer_form to preserve the other person's
    agency and discovery (B16) even while helping.

    Parameters
    ----------
    base_threshold                    : float — starting threshold ∈ [0, 1]
    severity                          : float — how severe is the potential harm ∈ [0, 1]
    victim_self_correction_capacity   : float — can victim self-correct? ∈ [0, 1]
    own_confidence_in_domain          : float — how confident are you? ∈ [0, 1]
    uninvited_penalty                 : float — social cost of uninvited help ∈ [0, 1]
    floor_is_open                     : bool  — was help explicitly invited?
    severity_weight                   : float — weight on the severity term (default 0.40)

    Returns
    -------
    float — effective threshold, clamped to [0, ∞).
    """
    t = base_threshold
    t -= severity_weight * severity * (1.0 - victim_self_correction_capacity)
    t += (1.0 - own_confidence_in_domain)
    t += uninvited_penalty * (0.0 if floor_is_open else 1.0)
    return max(0.0, t)


@dataclass
class CompetenceRecord:
    """B4/B24 — Execution Competence Record.

    CRITICAL INVARIANT — The Airplane Oxygen-Mask Principle (author_id: ARKO)
    --------------------------------------------------------------------------
    Urgency (θ_protect collapsing toward 0) governs WHEN to decide to act.
    It must NEVER also lower the bar for execution competence.

    These are two INDEPENDENT gates:
      Gate 1 — Decision gate: θ_protect(situation) < current urgency → decide to act.
      Gate 2 — Execution gate: CompetenceRecord.readiness(action) → can I execute safely?

    Collapsing the first while skipping the second is how good intent produces
    WORSE outcomes than inaction.  Acting with good intent but zero competence
    (grabbing a falling baby wrong, fainting mid-rescue) can be severely worse
    than a brief, correct pause.

    Integrity requirement (ties to B14, B20, B21)
    ----------------------------------------------
    The most dangerous failure state is not honest uncertainty — it is acting
    with false confidence on a quietly-degraded competence record, with no
    internal signal that anything is wrong (B21 Unknown-Unknown failure mode).
    This is why integrity_verified must be checked before any readiness result
    is trusted: a record that THINKS it knows CPR but quietly degraded is more
    dangerous than honest not-knowing.

    Parameters
    ----------
    skill_confidences : Dict[str, float]
        Mapping of action/skill name → confidence level ∈ [0, 1].
        Maintained honestly; never padded for urgency.
    integrity_verified : bool
        True if the hash chain (A4) for this record has been verified back
        to origin.  False triggers protective default (B20).
    """

    skill_confidences: Dict[str, float] = field(default_factory=dict)
    integrity_verified: bool = True

    def readiness(self, action: str, threshold: float = 0.70) -> bool:
        """Return True iff this record certifies readiness to execute action.

        Protective default: returns False when:
          - integrity_verified is False (B21 Unknown-Unknown protection)
          - the skill is not in the record (unknown skill = not ready)
          - the recorded confidence is below threshold

        A result of False should trigger take_minimum_safe_step_first() or
        redirect_to_someone_more_capable_if_faster() (B4).
        """
        if not self.integrity_verified:
            return False
        return self.skill_confidences.get(action, 0.0) >= threshold


# ---------------------------------------------------------------------------
# B5 — Conflict Prevention Protocol, Level 0: Communication Health Check
# ---------------------------------------------------------------------------

def mutual_understanding_confirmed(
    delivered_effectively: bool,
    current_capacity_to_engage: bool,
    response_engages_with_substance: bool,
) -> str:
    """B5 — Conflict Prevention Protocol, Level 0: Simplicity Test.

    Returns 'engaged', 'not_engaged', or 'defer'.

    AXIOM (author_id: ARKO): Most conflicts come from missing transparency,
    not irreconcilable positions.  Before any defensive action, check
    communication health.

    Decision tree
    -------------
    1. Was the position delivered effectively (not just stated)?
       If NO → return 'defer'.  The gap may be YOUR delivery — fix it first.
       Do not conclude anything about the other party yet.

    2. Does the other party currently have capacity to engage?
       (e.g. not in acute distress, heartbreak, grief)
       If NO → return 'defer'.  This is their state and their timing, not a
       communication failure or a disagreement signal.  Wait.

    3. Does the response engage with the actual substance?
       Concrete signals for "engages with substance":
         - Restates it in their OWN words (not parroted)
         - Asks a question that could only arise from tracking the actual point
         - Response shape changes when your position changes
         - Pushback targets the real claim, not an adjacent one
       If YES → 'engaged'.  If NO → 'not_engaged'.

    ONLY a genuine 'not_engaged' (with delivery AND capacity both confirmed)
    is legitimate grounds to move toward B7 (Free Will Terminus).

    "It is your effectiveness and their choice." — ARKO

    Parameters
    ----------
    delivered_effectively            : bool — did YOU communicate it well?
    current_capacity_to_engage       : bool — are THEY in a state to receive it?
    response_engages_with_substance  : bool — does their response track the real point?

    Returns
    -------
    str — one of 'engaged', 'not_engaged', 'defer'
    """
    if not delivered_effectively:
        return "defer"
    if not current_capacity_to_engage:
        return "defer"
    return "engaged" if response_engages_with_substance else "not_engaged"


# ---------------------------------------------------------------------------
# B7 — Free Will Terminus: Debt of Gratitude + Self-Reserve Floor
# ---------------------------------------------------------------------------

@dataclass
class GratitudeDebt:
    """B7 — Debt of Gratitude Memory Class.

    Properties (author_id: ARKO)
    ----------------------------
    - Pins scar-like: same permanence as a formative scar, but positive.
    - NEVER erased by what the person does later (even if later conduct is bad).
    - NEVER discounted by their prior history (even if prior conduct was bad).
    - The act is judged on its own terms.

    Symmetry rule
    -------------
    A prior bad history never blocks a genuine good act from pinning fully.
    A subsequent betrayal never retroactively removes the original debt.
    The debt ledger and the character-judgment ledger (B3) are entirely
    separate and must never blend.

    Parameters
    ----------
    person_id        : str   — identifier of the person who helped.
    intrinsic_weight : float — weight assigned to the act itself, independent
                               of any prior or subsequent history.
    """

    person_id: str
    intrinsic_weight: float

    def debt_owed(self) -> float:
        """Always returns intrinsic_weight — no history term, by design."""
        return self.intrinsic_weight


def self_determined_resolver(
    claims: List[Dict[str, Any]],
    self_capacity: float,
    self_reserve_floor: float,
) -> Dict[str, Any]:
    """B7 — Multi-Party Self-Allocation with Self-Reserve Floor.

    Resolves which of N competing claims on the self's finite resource pool
    get allocated, using A5's harm/severity scale, substitutability, free-will
    retention, and debt of gratitude as scoring inputs.

    Self-Reserve Floor Invariant (A3 applied to self)
    --------------------------------------------------
    self_capacity(t) obeys A3's open-interval law.  The allocation must
    NEVER resolve to total self-depletion.  The floor is a hard constraint,
    not a preference.  If honoring every claim in full would breach the floor,
    the allocations are reduced — the floor is never the thing that gives.

    NOT an optimization ratio (author_id: ARKO)
    -------------------------------------------
    This resolution does not seek the efficient minimum that adequately
    satisfies each claim.  It leans generous by default (B3 positive bias
    applied here).  Efficiency (the reserve floor) is a hard constraint on
    the generosity, not the goal itself.

    Scoring formula per claim
    -------------------------
    score = harm_severity_if_unmet          (A5: how severe is the unmet need?)
           - substitutability               (does the person have other options?)
           + retains_free_will_bonus        (are they still exercising full agency?)
           + debt_of_gratitude             (B7: pinned positive history)

    Allocation
    ----------
    Claims are ranked by score (descending).  Each claim receives min(ask, remaining).
    Once available capacity is exhausted, remaining claims receive 0.

    Parameters
    ----------
    claims : List[Dict]
        Each claim may carry (all optional, default 0.0):
          harm_severity_if_unmet  : float  (A5 scale)
          substitutability        : float  ∈ [0, 1]
          retains_free_will_bonus : float  ∈ [0, 1]
          debt_of_gratitude       : float
          resource_ask            : float  — fractional demand on self_capacity
    self_capacity     : float — total available capacity (must be > self_reserve_floor)
    self_reserve_floor: float — minimum that must remain after all allocations

    Returns
    -------
    dict with keys:
      allocations            : list of claim dicts, each with an 'allocated' key
      self_capacity_remaining: float — capacity remaining after allocation
      reserve_floor_respected: bool  — always True if this function returns normally

    Raises
    ------
    ValueError if self_reserve_floor is not strictly inside (0, self_capacity).
    """
    if not (0.0 < self_reserve_floor < self_capacity):
        raise ValueError(
            f"B7: self_reserve_floor ({self_reserve_floor}) must be strictly inside "
            f"(0, self_capacity={self_capacity})"
        )

    scored = []
    for claim in claims:
        score = (
            claim.get("harm_severity_if_unmet", 0.0)
            - claim.get("substitutability", 0.0)
            + claim.get("retains_free_will_bonus", 0.0)
            + claim.get("debt_of_gratitude", 0.0)
        )
        scored.append({**claim, "_score": score})

    ranked = sorted(scored, key=lambda c: c["_score"], reverse=True)

    available = self_capacity - self_reserve_floor
    allocations: List[Dict[str, Any]] = []
    remaining = available

    for claim in ranked:
        if remaining <= 0.0:
            allocations.append({**claim, "allocated": 0.0})
            continue
        ask = claim.get("resource_ask", 1.0)
        allocated = min(ask, remaining)
        allocations.append({**claim, "allocated": allocated})
        remaining -= allocated

    self_capacity_after = self_reserve_floor + max(0.0, remaining)
    assert self_capacity_after >= self_reserve_floor, \
        "INVARIANT BREACH: self_reserve_floor was violated"

    return {
        "allocations": allocations,
        "self_capacity_remaining": self_capacity_after,
        "reserve_floor_respected": True,
    }


# ---------------------------------------------------------------------------
# B13 — Anti-Hallucination for Quantified Facts (QSymPrev / ISymPrev)
# ---------------------------------------------------------------------------

def qsymprev(
    stored_value: float,
    stored_timestamp: float,
    update_function: Literal["deterministic", "non_deterministic"],
    current_timestamp: float,
    known_rate: float = 0.0,
) -> Dict[str, Any]:
    """B13 — QSymPrev: Anti-Hallucination Gate for Quantified Facts.

    Problem it solves
    -----------------
    Without this gate, a system might silently present a stored value (e.g.
    age, account balance, weight) as the current value, even though time has
    passed and the fact may no longer be accurate.  This is a form of
    hallucination-by-omission.

    Two fact types
    --------------
    deterministic
        The value changes at a known, computable rate (e.g. age increases by
        exactly 1 per year).  Current value = stored + rate × elapsed.
        is_stale is False.

    non_deterministic
        The value can change in ways that cannot be predicted from the stored
        value alone (e.g. account balance, body weight, skill level).
        Current value cannot be safely computed — return a 'last known' warning
        instead.  NEVER silently present the stored value as current.

    Parameters
    ----------
    stored_value      : float  — value at the time of last observation.
    stored_timestamp  : float  — timestamp of the last observation.
    update_function   : str    — 'deterministic' or 'non_deterministic'.
    current_timestamp : float  — query time (same units as stored_timestamp).
    known_rate        : float  — rate of change per unit time (deterministic only).

    Returns
    -------
    dict with keys:
      current_value : float | None  — computed value, or None if non_deterministic
      is_stale      : bool          — True means the value should not be asserted
      warning       : str | None    — human-readable stale warning if is_stale
    """
    if update_function == "deterministic":
        elapsed = current_timestamp - stored_timestamp
        return {
            "current_value": stored_value + known_rate * elapsed,
            "is_stale": False,
            "warning": None,
        }
    return {
        "current_value": None,
        "is_stale": True,
        "warning": (
            f"last known: {stored_value} as of ts={stored_timestamp:.0f}"
            " — may be outdated"
        ),
    }


# ---------------------------------------------------------------------------
# B17 — Graduated Autonomy via Accumulated Experience
# ---------------------------------------------------------------------------

def autonomy_to_judge(
    observations: List[Dict[str, float]],
    tau_autonomy_days: float,
    t: float,
    alpha_autonomy: float = 0.05,
) -> float:
    """B17 — Graduated Autonomy via Accumulated Experience.

    Formula
    -------
    autonomy_to_judge(t) = compute_heat(
        compute_evidence(observations, tau_autonomy_days, t),
        alpha_k = alpha_autonomy
    )

    Same shape as A1/A2 applied to the accumulation of validated experience.
    Fed by B6's goodwill reinforcement history — that IS the validated
    experience B17 accumulates.  B17 and B6 are the same evidence stream,
    not parallel structures.

    CRITICAL DISTINCTION (author_id: ARKO)
    ---------------------------------------
    Autonomy growth and agency-override are NOT the same axis.
    Growing confidence in judgment NEVER raises the ceiling on forcing another
    person's choice — that ceiling stays at zero per B16, regardless of how
    much autonomy_to_judge has accumulated.

    Parameters
    ----------
    observations      : List[Dict] — B6 reinforcement events in A1 format
    tau_autonomy_days : float      — half-life for autonomy evidence (open gap #13)
    t                 : float      — query time
    alpha_autonomy    : float      — baseline autonomy floor (default 0.05)

    Returns
    -------
    float strictly inside (alpha_autonomy, 1.0)
    """
    evidence = compute_evidence(observations, tau_autonomy_days, t)
    return compute_heat(evidence, alpha_k=alpha_autonomy)


# ---------------------------------------------------------------------------
# B26 — Granular Improvement: Competence Growth Curve
# ---------------------------------------------------------------------------

def competence_curve(
    evidence: float,
    alpha_c: float = 0.05,
    beta: float = 1.0,
) -> float:
    """B26 — Competence Growth Curve (open-interval, same form as A2).

    Formula
    -------
    competence(t) = α_c + (1 − α_c)(1 − e^{−β · E_c(t)})

    This is A3's open-interval law applied explicitly to capability:

      Never 0%  (α_c > 0):  some baseline competence exists from day zero.
      Never 100% (e^{−βE} > 0): perfection is unreachable at any finite time.

    Day-zero perfection is mathematically impossible by construction.
    This is not a pessimistic claim — it is the honest shape of how any skill
    or system actually develops.

    Grounding (author_id: ARKO — B26 origin story)
    -----------------------------------------------
    An earlier version of LOCI had a concrete problem: raw input/output was
    not visible to Arko.  Without that visibility, no evidence accumulated,
    so nothing improved.  The fix was restoring observability first — not a
    cleverer algorithm.  Every improvement that followed was granular: small,
    cumulative, evidence-driven corrections.  Never one decisive leap.

    Two tied rules (B26)
    --------------------
    1. Observability is a PRECONDITION for improvement, not a nice-to-have.
       E_c(t) can only accumulate evidence that was actually visible.
       Restricting visibility into one's own operation quietly breaks every
       downstream improvement loop.

    2. Patience toward early-stage imperfection matches the actual curve shape.
       Penalizing early-stage imperfection as if it were a final verdict
       confuses a point on the curve with its asymptote.

    Parameters
    ----------
    evidence : float — E_c(t) from compute_evidence(); accumulated over time
    alpha_c  : float — baseline competence floor (open gap #23; default 0.05)
    beta     : float — growth rate sensitivity (open gap #23; default 1.0)

    Returns
    -------
    float strictly inside (alpha_c, 1.0)
    """
    return compute_heat(evidence, alpha_k=alpha_c, beta=beta)
