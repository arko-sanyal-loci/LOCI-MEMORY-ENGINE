#!/usr/bin/env python3
"""Bounded numeric dream stream.

This is a NUMERICAL DEMO evaluator: it scores caller-supplied arithmetic
candidates and keeps a fixed handful. It does not generate agent plans,
trades, or market paths. Winners stay quarantined simulated candidates.
Semantic candidate generation needs an embedding or language-model adapter;
this module does not invent one.
"""

from __future__ import annotations

import heapq
import time
from typing import Callable, Dict, List


QUARANTINE = "DSymPrev"
EPISTEMIC_CONFIDENCE = 0.0


def stream_evaluate(
    count: int,
    evaluate: Callable[[int], tuple],
    *,
    keep: int = 2,
    batch_size: int = 20000,
) -> Dict:
    """Evaluate `count` candidates without storing them all.

    `evaluate(i)` returns `(candidate_id, score)`. Higher score is better
    inside this stream only. The score is not an observed outcome.
    """
    if count < 0:
        raise ValueError("count must be >= 0")
    if keep < 1:
        raise ValueError("keep must be >= 1")
    if batch_size < 1:
        raise ValueError("batch_size must be >= 1")

    heap: List[tuple] = []
    seen = 0
    started = time.perf_counter()
    for start in range(0, count, batch_size):
        end = min(count, start + batch_size)
        for index in range(start, end):
            candidate_id, score = evaluate(index)
            score_f = float(score)
            seen += 1
            entry = (score_f, seen, candidate_id)
            if len(heap) < keep:
                heapq.heappush(heap, entry)
            elif score_f > heap[0][0]:
                heapq.heapreplace(heap, entry)
    elapsed = time.perf_counter() - started
    winners = []
    for score, _seq, candidate_id in sorted(heap, key=lambda row: -row[0]):
        winners.append(
            {
                "id": candidate_id,
                "score": score,
                "epistemic_confidence": EPISTEMIC_CONFIDENCE,
                "stream_quarantine": QUARANTINE,
                "provenance_kind": "simulated_candidate",
                "epistemic_status": "candidate",
                "label": "NUMERICAL_DEMO",
            }
        )
    return {
        "label": "NUMERICAL_DEMO",
        "not_agent_plans": True,
        "not_verified_facts": True,
        "evaluated": seen,
        "retained": len(winners),
        "elapsed_seconds": elapsed,
        "winners": winners,
        "semantic_generation": {
            "status": "missing_capability",
            "service": "embedding_or_language_model",
            "detail": (
                "No model adapter was configured. Geodesic dream pairs were "
                "not filled with fabricated embeddings."
            ),
        },
    }
