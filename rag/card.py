"""Category-Adaptive Recall Depth (CARD).

Implements the portable core of the CARD scheme described in
"Category-Adaptive Recall Depth (CARD) for Heat-Tiered Memory Systems"
(Sanyal, 2026, TDCommons #10856): retrieval depth K and ranking strategy
are conditioned on a query category, assigned by the shared deterministic
keyword heuristic used by both RAG and live-session recall.

This module ranks knowledge_update results by real heat from
`loci_engine.vectors.VectorStore` (recency as a tie-break when heat is
equal or absent), and temporal_reasoning results by document metadata
dates - there is still no entity co-occurrence graph or fact versioning
consumed here beyond heat itself. Multi-session and temporal RAG additionally
follow bounded adjacent chunks from the same source and page.
"""

from loci_engine.card_categories import classify_query_category

RECALL_DEPTH = {
    "information_extraction": 5,
    "knowledge_update": 3,
    "multi_session_reasoning": 10,
    "temporal_reasoning": 7,
}

def recall_depth(category: str) -> int:
    return RECALL_DEPTH[category]


def apply_ranking_strategy(category: str, results: list[dict]) -> list[dict]:
    if category == "knowledge_update":
        return sorted(
            results,
            key=lambda r: (
                r.get("heat", 0.0),
                r.get("metadata", {}).get("moddate")
                or r.get("metadata", {}).get("creationdate")
                or "",
            ),
            reverse=True,
        )
    if category == "temporal_reasoning":
        return sorted(
            results,
            key=lambda r: r["metadata"].get("creationdate")
            or r["metadata"].get("moddate")
            or "",
        )
    return results
