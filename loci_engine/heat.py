#!/usr/bin/env python3
"""
loci_engine/heat.py
====================
LOCI Learning Core — domain-neutral evidence/decay mathematics (A1-A3).

This is the single source of truth for the open-interval hyperbolic
activation law that the rest of LOCI builds ethical, trust, and competence
meaning on top of.  It has no concept of "ethical," "scar," or "trust" —
it only knows about evidence accumulating and decaying over time.

  heat.py            — THIS module. Pure math. No ethics vocabulary.
  ethical_core.py    — Ethics Core. Adds scars, vengeance, competence gates,
                        etc. on top of this module's two primitives.
  ethics.py          — observe-only valence/conflict/trust/provenance layer,
                        the newest consumer, reusing this module directly
                        rather than re-deriving the decay law.
  store.py           — entity persistence for anything that needs its heat
                        tracked over time (trust patterns, scars, etc.),
                        backed by the same context2.db storage.py manages.

AUTHOR PROVENANCE
------------------
author_ids: ARKO (definitions, principles), ARC (math formalization),
            CLAUDE (session implementation)

OPEN-INTERVAL INVARIANT (A3)
-----------------------------
No quantity derived from this module ever reaches its theoretical extreme:

  evidence_heat(e, alpha, beta)  strictly inside (alpha, 1.0)

Clamping either bound breaks both the math and the philosophy behind it —
see the loci-ethical-reasoning-core skill document for the full
philosophical spine. Every higher layer (scar heat, competence curves,
autonomy, self-capacity) is this same curve applied to a different kind
of evidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Sequence, Tuple


# ===========================================================================
# B1 — Memory Spectrum: standard half-life / floor pairs
# ===========================================================================

@dataclass(frozen=True)
class MemoryClass:
    """One row in the Memory Spectrum table.

    name     : human-readable class name
    tau_days : decay half-life in days (τ_k in A1/A2)
    alpha    : Constant of Hope floor (α_k in A2/A3) — strictly inside (0, 1)
    """

    name: str
    tau_days: float
    alpha: float


MEMORY_CLASSES: Dict[str, MemoryClass] = {
    # Formative scars are the stickiest: τ=45d keeps the protective
    # pattern hot for six weeks, and α=0.14 ensures it never fully fades.
    "formative_scar": MemoryClass("formative_scar", tau_days=45.0, alpha=0.14),
    # Valued skills decay slower than routine observations; tracks
    # competence accumulation.
    "valued_skill": MemoryClass("valued_skill", tau_days=20.0, alpha=0.08),
    # Routine observations are meant to fade quickly.
    "routine_observation": MemoryClass("routine_observation", tau_days=3.0, alpha=0.05),
}

# ===========================================================================
# B2 — Hardware Tier Schema (empirically validated by Spark, Nov 2026)
#
# Tier boundaries and tau values come from heat_schema.py and were confirmed
# by Spark's 300-trial parameter sweep (playground/fine_grained_sweep.py).
# θ_HOT=0.700 is the VRAM working-set admission threshold (not the tier
# boundary); tier classification uses the values below.
# ===========================================================================

ALPHA_FLOOR: float = 0.0500   # Constant of Hope — heat never reaches zero
HEAT_CEILING: float = 0.9999  # Open-interval ceiling — heat never reaches 1.0
VRAM_ADMISSION_THRESHOLD: float = 0.700  # θ_HOT proven optimal by Spark sweep

# Heat tier classification boundaries and their associated decay tau (days).
# Tier tau is how quickly an item decays through that tier when unaccessed.
TIER_HOT_BOUNDARY: float = 0.8000   # H >= this → HOT  (VRAM active working set)
TIER_MILD_BOUNDARY: float = 0.3500  # H >= this → MILD (Host RAM arena)
                                     # H <  this → COLD (NVMe archival ledger)

TIER_TAU: Dict[str, float] = {
    "hot":  1.25,  # days — recency-sensitive; cools within ~1.25 days unaccessed
    "mild": 1.75,  # days — intermediate decay
    "cold": 2.25,  # days — archival; preserved longer before eviction
}


# ===========================================================================
# A1 — Evidence Accumulation
# ===========================================================================

def evidence_accumulation(
    events: Sequence[Tuple[float, float, float]],
    *,
    now: float,
    tau: float | None = None,
) -> float:
    """A1 — Evidence Accumulation.

    Formula
    -------
    E_k(t) = Σ_{j, t_j ≤ t}  r_j · w_j / (1 + (t − t_j) / τ_k)

    The denominator grows hyperbolically with elapsed time, so every past
    observation contributes a nonzero amount forever — evidence decays but
    NEVER reaches zero.

    Parameters
    ----------
    events : sequence of (t_j, relevance, valence_weight) triples
        t_j            — timestamp of the observation (same units as now)
        relevance      — relevance weight, typically in [0, 1]
        valence_weight — signed weight (positive = good signal, negative = bad)
    now : query time. Observations with t_j > now are silently ignored.
    tau : half-life. Defaults to the formative_scar half-life (45 days) —
        callers tracking a different memory class should pass its tau_days
        explicitly via MEMORY_CLASSES[name].tau_days.

    Returns
    -------
    float — accumulated evidence E_k(now).
    """
    if tau is None:
        tau = MEMORY_CLASSES["formative_scar"].tau_days
    total = 0.0
    for t_j, relevance, valence_weight in events:
        if t_j <= now:
            dt = max(0.0, now - t_j)
            total += (relevance * valence_weight) / (1.0 + dt / tau)
    return total


# ===========================================================================
# A2/A3 — Heat Activation (open-interval thermodynamics)
# ===========================================================================

def evidence_heat(
    evidence: float,
    *,
    alpha: float | None = None,
    beta: float = 1.0,
) -> float:
    """A2/A3 — Heat Activation (open-interval thermodynamics).

    Formula
    -------
    H_k(t) = α_k + (1 − α_k)(1 − e^{−β · E_k(t)})

    Open-Interval Proof (A3)
    -------------------------
    - NEVER 0%:   α_k > 0 is the floor every heat value approaches but
                  never crosses as evidence → 0 — the "Constant of Hope."
    - NEVER 100%: e^{−βE} > 0 for all finite E, so heat < 1.0 always.
                  A fresh formative scar peaks at ≈0.912 and immediately
                  begins cooling.

    This is the universal activation curve in LOCI: the same shape governs
    scar heat, trust heat, self-capacity, competence growth, and autonomy.

    Parameters
    ----------
    evidence : E_k(t) from evidence_accumulation(); must be >= 0.
    alpha    : Constant of Hope floor, strictly inside (0, 1). Defaults to
        the formative_scar alpha (0.14) — callers tracking a different
        memory class should pass MEMORY_CLASSES[name].alpha explicitly.
    beta     : sensitivity parameter (default 1.0).

    Returns
    -------
    float strictly inside (alpha, 1.0).

    Raises
    ------
    ValueError if alpha is not strictly inside (0, 1).
    """
    if alpha is None:
        alpha = MEMORY_CLASSES["formative_scar"].alpha
    if not (0.0 < alpha < 1.0):
        raise ValueError(
            f"alpha must be strictly inside (0, 1) to preserve the "
            f"open-interval invariant (A3); got {alpha}"
        )
    raw = alpha + (1.0 - alpha) * (1.0 - math.exp(-beta * max(0.0, evidence)))
    # Nudge away from the bounds by the smallest representable increment so
    # the open-interval invariant holds even at evidence = 0 or evidence = inf.
    return max(alpha + 1e-9, min(1.0 - 1e-9, raw))


def decay(heat_value: float, elapsed: float, tau: float) -> float:
    """Simple one-shot hyperbolic decay: h / (1 + elapsed/tau).

    This is the *simpler* cousin of evidence_accumulation/evidence_heat —
    useful when a caller already has a single scalar heat value and just
    needs to age it forward, rather than re-deriving heat from a full
    evidence history. Scar heat deliberately does NOT use this function;
    it always re-derives from the full event history via
    evidence_accumulation/evidence_heat so B2's "never 0%, never 100%"
    guarantee holds structurally rather than by convention.
    """
    return heat_value / (1.0 + elapsed / tau)


def tier(heat_value: float) -> str:
    """Map a heat value to the canonical 3-tier hardware routing label.

    Boundaries from heat_schema.py, validated by Spark's Nov 2026 sweep.
    hot  → VRAM active working set  (H >= 0.8000)
    mild → Host RAM SymLinkPrev     (H >= 0.3500)
    cold → NVMe archival ledger     (H <  0.3500)
    """
    if heat_value >= TIER_HOT_BOUNDARY:
        return "hot"
    if heat_value >= TIER_MILD_BOUNDARY:
        return "mild"
    return "cold"
