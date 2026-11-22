"""Category-Adaptive Recall Depth (CARD).

Implements the portable core of the CARD scheme described in
"Category-Adaptive Recall Depth (CARD) for Heat-Tiered Memory Systems"
(Sanyal, 2026, TDCommons #10856): retrieval depth K and ranking strategy
are conditioned on a query category, assigned by a rule-based keyword
heuristic (one of the three classification options the paper allows).

All categories use a hybrid ranking policy. Explicit user ground truth is
always preferred, followed by TRS/semantic-stream evidence, heat, and
recency. Category-specific ordering remains a tie-breaker, so temporal
results stay chronological where the stronger signals are equal.

The optional ``metadata["trs_final_package"]`` contract is deliberately
small: it may contain ``stream_score``/``semantic_score`` or a ``streams``
mapping whose values contain ``score``/``relevance``. This lets callers
extrapolate from a trusted TRS package without making the vector store
depend on the package format.
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


def _metadata(result: dict) -> dict:
    value = result.get("metadata", {})
    return value if isinstance(value, dict) else {}


def _is_user_ground_truth(result: dict) -> bool:
    metadata = _metadata(result)
    return bool(
        result.get("user_ground_truth")
        or metadata.get("user_ground_truth")
        or metadata.get("provenance") == "user_stated"
    )


def _stream_score(result: dict) -> float:
    metadata = _metadata(result)
    package = metadata.get("trs_final_package")
    if not isinstance(package, dict):
        package = metadata.get("trs") if isinstance(metadata.get("trs"), dict) else {}

    candidates = [
        result.get("stream_score"),
        metadata.get("stream_score"),
        metadata.get("semantic_score"),
        package.get("stream_score"),
        package.get("semantic_score"),
        package.get("relevance"),
    ]
    streams = package.get("streams")
    if isinstance(streams, dict):
        for value in streams.values():
            if isinstance(value, dict):
                candidates.extend((value.get("score"), value.get("relevance")))
            elif isinstance(value, (int, float)):
                candidates.append(value)
    scores = [float(value) for value in candidates
              if isinstance(value, (int, float)) and not isinstance(value, bool)]
    return max(scores, default=0.0)


def _category_tiebreak(category: str, result: dict) -> tuple:
    metadata = _metadata(result)
    date = metadata.get("creationdate") or metadata.get("moddate") or ""
    if category == "temporal_reasoning":
        return (date,)
    return (metadata.get("moddate") or metadata.get("creationdate") or "",)


def apply_ranking_strategy(category: str, results: list[dict]) -> list[dict]:
    """Rank results with provenance-first hybrid adaptive recall.

    ``sorted`` is stable, so callers retain vector retrieval order when all
    explicit ranking signals are absent.
    """
    # Establish the category-specific ordering first. The stable second sort
    # then gives provenance, stream evidence, and heat precedence while
    # retaining chronology/recency when those signals are equal.
    ranked = sorted(
        results,
        key=lambda result: _category_tiebreak(category, result),
        reverse=category != "temporal_reasoning",
    )
    return sorted(
        ranked,
        key=lambda result: (
            1 if _is_user_ground_truth(result) else 0,
            _stream_score(result),
            result.get("heat", 0.0),
        ),
        reverse=True,
    )
