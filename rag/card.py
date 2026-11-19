"""Category-Adaptive Recall Depth (CARD).

Implements the portable core of the CARD scheme described in
"Category-Adaptive Recall Depth (CARD) for Heat-Tiered Memory Systems"
(Sanyal, 2026, TDCommons #10856): retrieval depth K and ranking strategy
are conditioned on a query category, assigned by a rule-based keyword
heuristic (one of the three classification options the paper allows).

This module ranks knowledge_update results by real heat from
`loci_engine.vectors.VectorStore` (recency as a tie-break when heat is
equal or absent), and temporal_reasoning results by document metadata
dates - there is still no entity co-occurrence graph or fact versioning
consumed here beyond heat itself, so multi_session_reasoning still only
gets the deeper K without graph-hop expansion (tracked as a later plan).
"""

RECALL_DEPTH = {
    "information_extraction": 5,
    "knowledge_update": 3,
    "multi_session_reasoning": 10,
    "temporal_reasoning": 7,
}

_KNOWLEDGE_UPDATE_KEYWORDS = (
    "update", "updated", "change", "changed", "now", "current",
    "currently", "latest", "revised", "as of",
)
_TEMPORAL_KEYWORDS = (
    "when", "before", "after", "history", "over time", "timeline",
    "previously", "used to", "evolve", "evolution",
)
_MULTI_SESSION_KEYWORDS = (
    "compare", "across", "summarize", "summarise", "overall", "combine",
    "synthesize", "synthesise", "throughout", "every",
)


def classify_query_category(question: str) -> str:
    q = question.lower()
    if any(keyword in q for keyword in _KNOWLEDGE_UPDATE_KEYWORDS):
        return "knowledge_update"
    if any(keyword in q for keyword in _TEMPORAL_KEYWORDS):
        return "temporal_reasoning"
    if any(keyword in q for keyword in _MULTI_SESSION_KEYWORDS):
        return "multi_session_reasoning"
    return "information_extraction"


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
