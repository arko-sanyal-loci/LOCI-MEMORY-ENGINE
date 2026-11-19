"""Heat helpers for RAG chunks (ported from loci-memory-engine-1, 2026-11-19).

Chunk heat in the document store uses the original prototype model: exponential
decay at 0.95/day and hop-weighted increments. It is deliberately separate from
loci_engine.heat, whose hyperbolic, floor-bounded model governs agent memory.
Unifying the two is an open design task, so this module keeps the behaviour the
RAG pipeline was tested against instead of silently changing it.
"""

HEAT_MIN = 0.0
HEAT_MAX = 1.0
DECAY_RATE_PER_DAY = 0.95
HOP_INCREMENTS = {0: 0.5, 1: 0.25, 2: 0.125, 3: 0.0625}


def decay(heat: float, days_elapsed: float) -> float:
    decayed = heat * (DECAY_RATE_PER_DAY ** days_elapsed)
    return max(HEAT_MIN, decayed)


def apply_increment(heat: float, hop: int) -> float:
    k = HOP_INCREMENTS[hop]
    return heat + (1.0 - heat) * k


def tier(heat: float) -> str:
    if heat > 0.5:
        return "HOT"
    if heat > 0.167:
        return "MILD"
    return "COLD"
