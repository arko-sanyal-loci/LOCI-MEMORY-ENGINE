"""Shared keyword baseline for LOCI's category-adaptive recall routing.

This is an explicit, deterministic heuristic, not a learned semantic grader.
RAG and live-session recall share it so the same question receives the same
CARD category in both paths.
"""

import re

KNOWLEDGE_UPDATE_KEYWORDS = (
    "update", "updated", "change", "changed", "now", "current",
    "currently", "latest", "revised", "as of", "supersede", "revision",
)
TEMPORAL_KEYWORDS = (
    "when", "before", "after", "history", "over time", "timeline",
    "previously", "used to", "evolve", "evolution", "earlier", "since",
)
MULTI_SESSION_KEYWORDS = (
    "why", "how did", "connect", "across", "relationship", "synthesize",
    "synthesise", "root cause", "compare", "summarize", "summarise",
    "overall", "combine", "throughout", "every", "related", "adjacent",
    "neighborhood", "neighbourhood", "nearby", "conversation", "thread",
)


def classify_query_category(question: str) -> str:
    """Classify a query with precedence: update, temporal, multi-session, info."""
    q = re.sub(r"[^a-z0-9]+", " ", question.lower()).strip()
    if any(re.search(rf"\b{re.escape(keyword)}\b", q) for keyword in KNOWLEDGE_UPDATE_KEYWORDS):
        return "knowledge_update"
    if any(re.search(rf"\b{re.escape(keyword)}\b", q) for keyword in TEMPORAL_KEYWORDS):
        return "temporal_reasoning"
    if any(re.search(rf"\b{re.escape(keyword)}\b", q) for keyword in MULTI_SESSION_KEYWORDS):
        return "multi_session_reasoning"
    return "information_extraction"
