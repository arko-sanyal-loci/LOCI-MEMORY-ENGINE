"""
loci_engine/tau_gate.py
=======================
Dynamic τ abstention gate (Guidance pillar).

Problem it solves
-----------------
A fixed z-score threshold (``Z_TAU``) for "is the fast-path answer good
enough, or should we escalate / abstain?" assumes every query produces the
same shape of activation distribution. It does not. A query against a
dense, on-topic session yields a sharp peak (the top hit means something);
an off-topic or adversarial query yields a flat field where every score is
noise. A fixed gate either over-abstains on the first or hallucinates on the
second.

Source
------
Design session recorded in Dropbox, ``Arc Guidance/Claude Artifacts/Part 2/
forge query.txt`` (2026-09-07). Three options were specified there; this
module implements all three and the combination that session chose:

  1. ``shape_tau``      distribution shape (flatness penalty, gap bonus).
                        Works on the first query, needs no history.
  2. ``confidence_tau`` per-entity confidence history (rolling accuracy of
                        the fast path against deep recall).
  3. ``QUERY_TYPE_TAU`` query-type base τ, here chosen from **temporal-graph
                        era labels** rather than keywords alone, per the
                        "temporal graph labeling mixed with query type
                        classifier" synthesis in the same session.

Combination (``dynamic_tau``): the query type sets the base, era coherence
and entity confidence multiply it, and the distribution shape adds its
correction. A query with **no temporal anchor** (no top hit belongs to a
known era) is treated as out-of-context and gets ``TAU_OOC = 3.5``
regardless of confidence, which is what makes adversarial queries abstain.

What is NOT from the source
---------------------------
The session's widget that gave the exact formal combination was not saved
(the transcript shows only "Rendering widget"). The multiplicative
composition below follows the prose ("they compose multiplicatively";
"HOT-era entity ... τ pushed down to ~0.87 (1.25 × 0.7 × coherence)") and
is reproduced by ``tests/test_tau_gate.py``. Treat the coefficients as a
starting point to tune against the MRR targets, not as measured values.

MRR targets (from the same session)
-----------------------------------
  SLP MRR / full-engine MRR  >= 0.90   (lossless escalation claim)
  absolute MRR               >= 0.50   (practical usefulness)
  adversarial MRR            >= 0.70   (abstention: expected=[] scores 1.0
                                        when the engine abstains)
Baseline then: SLP 0.18, full 0.26, adversarial 0.05.
``evaluate_mrr()`` scores a run against these.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Mapping, Optional, Sequence

from loci_engine.heat import TIER_HOT_BOUNDARY, TIER_MILD_BOUNDARY

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_TAU: float = 1.75
TAU_OOC: float = 3.5          # no temporal anchor → abstain unless overwhelming
TAU_MIN: float = 0.5
TAU_MAX: float = 4.0
MIN_SCORES_FOR_SHAPE: int = 8  # fewer hits than this → always escalate

QUERY_TYPE_TAU: Dict[str, float] = {
    "lookup": 1.25,       # "what port does X use?" — precise, relax the gate
    "descriptive": 1.75,  # "what is X?"
    "ambiguous": 2.25,    # very short / vague
    "adversarial": 3.0,   # out-of-scope signals ("who is the CEO of ...")
}

# Era temperature → multiplier on τ. A HOT era is coherent, current context.
ERA_COHERENCE: Dict[str, float] = {"hot": 0.85, "mild": 1.0, "cold": 1.25}

MRR_TARGETS: Dict[str, float] = {
    "slp_over_full": 0.90,
    "absolute": 0.50,
    "adversarial": 0.70,
}


# ---------------------------------------------------------------------------
# Option 1 — distribution shape
# ---------------------------------------------------------------------------

def shape_tau(scores: Sequence[float], base_tau: float = BASE_TAU) -> float:
    """τ from the shape of the score distribution (option 1).

    ``scores`` are similarity scores, highest first (order is enforced).
    Flat distributions (low std) raise τ by up to 1.5; a clear winner
    (large gap between #1 and #2) lowers it by up to 0.25. With fewer than
    ``MIN_SCORES_FOR_SHAPE`` scores there is not enough evidence to judge
    shape, so the gate returns a τ no z-score can pass (always escalate).
    """
    if len(scores) < MIN_SCORES_FOR_SHAPE:
        return 999.0
    sims = sorted(scores, reverse=True)
    mean = sum(sims) / len(sims)
    std = math.sqrt(sum((x - mean) ** 2 for x in sims) / len(sims)) or 1e-6
    gap = sims[0] - sims[1]
    flatness_penalty = max(0.0, (0.05 - std) / 0.05) * 1.5
    gap_bonus = min(0.5, gap / 0.05) * 0.5
    return base_tau + flatness_penalty - gap_bonus


def top_z_score(scores: Sequence[float]) -> float:
    """z-score of the best hit within its own result set."""
    if len(scores) < 2:
        return 0.0
    sims = sorted(scores, reverse=True)
    mean = sum(sims) / len(sims)
    std = math.sqrt(sum((x - mean) ** 2 for x in sims) / len(sims))
    return (sims[0] - mean) / std if std > 0 else 0.0


# ---------------------------------------------------------------------------
# Option 2 — per-entity confidence history
# ---------------------------------------------------------------------------

@dataclass
class ConfidenceTracker:
    """Rolling accuracy of the fast path, per entity.

    Call ``record(entity, correct)`` after every escalation: ``correct`` is
    whether the fast-path (preview) answer for that entity also appeared in
    the deep-recall result. Confidence starts at ``prior`` (0.5) and moves
    as an exponential moving average with weight ``alpha``; ~20 queries
    stabilise it, matching the source's estimate.
    """

    prior: float = 0.5
    alpha: float = 0.1
    _conf: Dict[str, float] = field(default_factory=dict)

    def get(self, entity: str) -> float:
        return self._conf.get(entity, self.prior)

    def record(self, entity: str, correct: bool) -> float:
        cur = self.get(entity)
        new = (1 - self.alpha) * cur + self.alpha * (1.0 if correct else 0.0)
        self._conf[entity] = new
        return new


def confidence_multiplier(confidences: Sequence[float]) -> float:
    """Map mean top-k confidence to a τ multiplier in [~0.6, 2.0].

    conf=1.0 → 1.0× base would leave reliable entities at base τ, which is
    what the source's option 2 formula does (``base * (2 - conf)``). The
    synthesis step pushes reliable HOT-era entities *below* base, so the
    multiplier here is ``1.4 - 0.8·conf`` (conf 0.875 → 0.70, the "0.7"
    in the source's worked example; conf 0 → 1.4; conf 1 → 0.6).
    """
    if not confidences:
        return 1.0
    top = list(confidences)[:5]
    avg = sum(top) / len(top)
    return 1.4 - 0.8 * max(0.0, min(1.0, avg))


def confidence_tau(confidences: Sequence[float], base_tau: float = BASE_TAU) -> float:
    """Option 2 on its own, exactly as specified: ``base · (2 − mean_conf)``."""
    if not confidences:
        return base_tau
    top = list(confidences)[:5]
    return base_tau * (2.0 - sum(top) / len(top))


# ---------------------------------------------------------------------------
# Option 3 — query type, informed by temporal-graph era labels
# ---------------------------------------------------------------------------

_LOOKUP_PREFIXES = ("what port", "what is the", "where is", "which port", "what version")
_ADVERSARIAL_WORDS = ("who", "when", "why", "how many", "revenue", "ceo")


def classify_query_type(query: str) -> str:
    """Keyword query-type classifier (the source's option 3 heuristic)."""
    q = query.lower().strip()
    if any(q.startswith(p) for p in _LOOKUP_PREFIXES):
        return "lookup"
    if len(q.split()) <= 2:
        return "ambiguous"
    if any(w in q for w in _ADVERSARIAL_WORDS):
        return "adversarial"
    return "descriptive"


def era_temperature(heat: float) -> str:
    """hot / mild / cold label for an era's mean heat (heat.py boundaries)."""
    if heat >= TIER_HOT_BOUNDARY:
        return "hot"
    if heat >= TIER_MILD_BOUNDARY:
        return "mild"
    return "cold"


def era_vote(hit_eras: Sequence[Optional[str]]) -> tuple[Optional[str], float]:
    """Majority era among the top hits and the share that voted for it.

    ``hit_eras`` is the era label (e.g. a session id or "2026-Q3") of each
    top hit, ``None`` when a hit has no era. Returns ``(None, 0.0)`` when no
    hit has an era — the query has no temporal anchor.
    """
    labelled = [e for e in hit_eras if e]
    if not labelled:
        return None, 0.0
    counts: Dict[str, int] = {}
    for e in labelled:
        counts[e] = counts.get(e, 0) + 1
    era, n = max(counts.items(), key=lambda kv: (kv[1], kv[0]))
    return era, n / len(hit_eras)


# ---------------------------------------------------------------------------
# Combination
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class GateDecision:
    tau: float
    z: float
    passed: bool              # True → trust the fast path; False → escalate/abstain
    query_type: str
    era: Optional[str]
    era_temperature: Optional[str]
    reason: str

    def as_dict(self) -> dict:
        return {
            "tau": round(self.tau, 4), "z": round(self.z, 4), "passed": self.passed,
            "query_type": self.query_type, "era": self.era,
            "era_temperature": self.era_temperature, "reason": self.reason,
        }


def dynamic_tau(
    query: str,
    scores: Sequence[float],
    *,
    hit_eras: Optional[Sequence[Optional[str]]] = None,
    era_heat: Optional[Mapping[str, float]] = None,
    confidences: Optional[Sequence[float]] = None,
) -> GateDecision:
    """Decide whether the top hit for ``query`` is trustworthy.

    Parameters
    ----------
    query       : the user's query text.
    scores      : similarity scores of the candidate hits (any order).
    hit_eras    : era label per hit, aligned with ``scores`` sorted
                  descending. ``None`` disables the temporal anchor check
                  (callers without era data get options 1+2+3 only).
    era_heat    : mean heat per era label (e.g. from ``StorageEngine``).
    confidences : fast-path confidence of each top hit's entity.
    """
    qtype = classify_query_type(query)
    z = top_z_score(scores)

    era = temp = None
    if hit_eras is not None:
        era, share = era_vote(hit_eras)
        if era is None:
            return GateDecision(TAU_OOC, z, z >= TAU_OOC, qtype, None, None,
                                "no temporal anchor (out of context)")
        temp = era_temperature((era_heat or {}).get(era, TIER_MILD_BOUNDARY))
        coherence = ERA_COHERENCE[temp] * (1.0 + 0.5 * (1.0 - share))
    else:
        coherence = 1.0

    base = QUERY_TYPE_TAU[qtype]
    conf_mult = confidence_multiplier(confidences or [])
    shape_adj = shape_tau(scores, base_tau=0.0) if len(scores) >= MIN_SCORES_FOR_SHAPE else None
    if shape_adj is None:
        return GateDecision(999.0, z, False, qtype, era, temp,
                            f"fewer than {MIN_SCORES_FOR_SHAPE} hits: escalate")

    tau = max(TAU_MIN, min(TAU_MAX, base * conf_mult * coherence + shape_adj))
    return GateDecision(tau, z, z >= tau, qtype, era, temp,
                        "z >= tau" if z >= tau else "z < tau")


# ---------------------------------------------------------------------------
# MRR evaluation against the targets
# ---------------------------------------------------------------------------

def reciprocal_rank(ranked_ids: Sequence[str], expected: Iterable[str]) -> float:
    """1/rank of the first expected id. Empty ``expected`` is an adversarial
    query: abstaining (empty ``ranked_ids``) scores 1.0, answering scores 0."""
    expected = set(expected)
    if not expected:
        return 1.0 if not ranked_ids else 0.0
    for i, rid in enumerate(ranked_ids, start=1):
        if rid in expected:
            return 1.0 / i
    return 0.0


def evaluate_mrr(
    fast_path: Sequence[tuple[Sequence[str], Sequence[str]]],
    full_engine: Sequence[tuple[Sequence[str], Sequence[str]]],
) -> dict:
    """Score two runs over the same benchmark against ``MRR_TARGETS``.

    Each run is a list of ``(ranked_ids, expected_ids)`` per query; queries
    with empty ``expected_ids`` form the adversarial subset.
    """
    def mrr(rows, adversarial: bool) -> float:
        sel = [reciprocal_rank(r, e) for r, e in rows if (not e) == adversarial]
        return sum(sel) / len(sel) if sel else float("nan")

    slp, full = mrr(fast_path, False), mrr(full_engine, False)
    adv = mrr(fast_path, True)
    ratio = slp / full if full and not math.isnan(full) else float("nan")
    return {
        "slp_mrr": slp, "full_mrr": full, "slp_over_full": ratio, "adversarial_mrr": adv,
        "meets": {
            "slp_over_full": ratio >= MRR_TARGETS["slp_over_full"],
            "absolute": slp >= MRR_TARGETS["absolute"],
            "adversarial": adv >= MRR_TARGETS["adversarial"],
        },
    }


__all__ = [
    "BASE_TAU", "TAU_OOC", "QUERY_TYPE_TAU", "MRR_TARGETS", "ConfidenceTracker",
    "GateDecision", "classify_query_type", "confidence_multiplier", "confidence_tau",
    "dynamic_tau", "era_temperature", "era_vote", "evaluate_mrr", "reciprocal_rank",
    "shape_tau", "top_z_score",
]
