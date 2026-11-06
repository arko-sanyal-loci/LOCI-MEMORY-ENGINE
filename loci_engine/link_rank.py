#!/usr/bin/env python3
"""Direct relevance versus link expansion.

Native retrieval in this repository orders FTS5 hits by bm25, then heat.
It does not walk a memory graph. A separate CPU overlap test showed that
summing neighbor scores lets high-degree boilerplate outrank a weaker-looking
but directly relevant item.

This module keeps that failure mode explicit and ranks with a capped mean
instead of a raw sum. The cap is a fixed property of the ranker, not a
threshold fit to a particular query. Links never become facts.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Mapping, Sequence


# A neighbor bonus cannot exceed this absolute amount. A direct gap larger
# than the cap cannot be overturned by degree.
DEFAULT_HOP_CAP = 0.05
DEFAULT_HOP_WEIGHT = 0.15


def naive_summed_hop(direct: float, neighbor_directs: Sequence[float]) -> float:
    """Raw sum. High degree dominates. Retained so tests can show the failure."""
    return float(direct) + float(sum(neighbor_directs))


def robust_combined(
    direct: float,
    neighbor_directs: Sequence[float],
    *,
    hop_weight: float = DEFAULT_HOP_WEIGHT,
    hop_cap: float = DEFAULT_HOP_CAP,
) -> float:
    """direct + min(cap, weight * mean(neighbor direct scores)).

    Degree does not increase the bonus: the mean is used, then clipped.
    """
    if hop_cap < 0.0:
        raise ValueError("hop_cap must be >= 0")
    if not neighbor_directs:
        bonus = 0.0
    else:
        mean_neighbor = sum(neighbor_directs) / len(neighbor_directs)
        bonus = min(hop_cap, hop_weight * mean_neighbor)
    return float(direct) + bonus


def rank_items(
    items: Sequence[Mapping],
    links: Mapping[str, Sequence[str]],
    *,
    method: str,
    hop_weight: float = DEFAULT_HOP_WEIGHT,
    hop_cap: float = DEFAULT_HOP_CAP,
) -> List[dict]:
    """Rank items that already carry id and direct_score.

    `links` maps an id to neighbor ids. Missing neighbors contribute nothing.
    `method` is 'direct', 'naive_sum', or 'robust'.
    """
    by_id = {str(item["id"]): item for item in items}
    ranked = []
    for item in items:
        item_id = str(item["id"])
        direct = float(item.get("direct_score", 0.0))
        neighbor_ids = list(links.get(item_id, ()))
        neighbor_scores = [
            float(by_id[nid].get("direct_score", 0.0))
            for nid in neighbor_ids
            if nid in by_id
        ]
        if method == "direct":
            combined = direct
        elif method == "naive_sum":
            combined = naive_summed_hop(direct, neighbor_scores)
        elif method == "robust":
            combined = robust_combined(
                direct, neighbor_scores, hop_weight=hop_weight, hop_cap=hop_cap
            )
        else:
            raise ValueError(f"unknown rank method {method!r}")
        ranked.append(
            {
                "id": item_id,
                "direct_score": direct,
                "neighbor_count": len(neighbor_scores),
                "combined_score": combined,
                "method": method,
            }
        )
    ranked.sort(key=lambda row: (-row["combined_score"], -row["direct_score"], row["id"]))
    return ranked


def overlap_coefficient(query_tokens: Iterable[str], doc_tokens: Iterable[str]) -> float:
    """|intersection| / |query tokens|. Labelled lexical overlap, not an embedding."""
    query = [tok for tok in query_tokens if tok]
    if not query:
        return 0.0
    doc = set(doc_tokens)
    hit = sum(1 for tok in query if tok in doc)
    return hit / len(query)
