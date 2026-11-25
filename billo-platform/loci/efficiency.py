"""
LOCI Token Efficiency Engine: Context Efficiency Ratio (CER) and Token Logging.
Contains the resolution for Bug #8 (un-inflated CER baseline based on total raw scanned entities).
"""

import hashlib
import sqlite3
from typing import Any, Dict, List, Optional

# Core LOCI token pricing weights
TOKEN_WEIGHTS: Dict[str, float] = {
    "by_tag_number": 0.25,    # Numeric entity pre-filtered via tag index
    "by_tag": 0.35,           # Non-numeric entity matched via tag index
    "by_value_number": 0.50,  # Direct numeric match (core standard)
    "by_value": 0.75,         # Direct string match
    "by_hint": 1.00,          # Context hint/occurrence scan
    "full_scan": 4.00,        # Baseline: Raw full context scan without LOCI index
}

REFERENCE_USD: float = 100.0  # Normalized dollar baseline for monetary savings


def query_hash(query_str: str) -> str:
    """Computes deterministic 16-character SHA-256 hash for query deduplication."""
    return hashlib.sha256(query_str.encode("utf-8")).hexdigest()[:16]


def weight_for_hit(entity_type: str, match_mode: str) -> float:
    """Calculates granular token cost for a single entity hit."""
    is_num = (entity_type == "number")
    if match_mode == "tag":
        return TOKEN_WEIGHTS["by_tag_number"] if is_num else TOKEN_WEIGHTS["by_tag"]
    elif match_mode == "value":
        return TOKEN_WEIGHTS["by_value_number"] if is_num else TOKEN_WEIGHTS["by_value"]
    elif match_mode == "hint":
        return TOKEN_WEIGHTS["by_hint"]
    return TOKEN_WEIGHTS["full_scan"]


def loci_token_cost(hits: List[Dict[str, Any]], hierarchy_nodes_scanned: int = 0) -> float:
    """
    Computes total effective LOCI token cost:
    Sum of hit weights + flat structural hierarchy traversal overhead (0.1/node).
    """
    total = sum(weight_for_hit(h.get("entity_type", "term"), h.get("match_mode", "value")) for h in hits)
    hierarchy_overhead = hierarchy_nodes_scanned * 0.10
    return round(total + hierarchy_overhead, 4)


def baseline_token_cost(total_raw_entities_scanned: int) -> float:
    """
    RESOLVES BUG #8:
    Calculates correct brute-force baseline cost.
    The denominator must represent the total raw context entity count in the scope,
    NOT the subset of entity hits returned by the query.
    """
    return round(float(total_raw_entities_scanned) * TOKEN_WEIGHTS["full_scan"], 4)


def efficiency_ratio(loci_cost: float, baseline_cost: float) -> float:
    """Computes Context Efficiency Ratio (CER). Protects against zero-division."""
    return round(baseline_cost / max(loci_cost, 0.05), 2)


def scale_rating(ratio: float) -> Dict[str, str]:
    """Evaluates CER performance tier, visual glyph, and performance note."""
    if ratio < 0.5:
        return {"grade": "POOR", "emoji": "⬛", "note": "LOCI index cost exceeds naive scan"}
    elif ratio < 1.0:
        return {"grade": "BELOW", "emoji": "🟥", "note": "Marginal efficiency benefit"}
    elif ratio < 2.0:
        return {"grade": "GOOD", "emoji": "🟧", "note": "1–2× efficiency improvement"}
    elif ratio < 5.0:
        return {"grade": "GREAT", "emoji": "🟨", "note": "2–5× efficient over raw scanning"}
    elif ratio < 10.0:
        return {"grade": "EXCELLENT", "emoji": "🟩", "note": "5–10× efficient — strong entity coverage"}
    else:
        return {"grade": "PEAK", "emoji": "🟦", "note": "Exceptional context compression (>10×)"}


def scale_bar(ratio: float, width: int = 20) -> str:
    """Renders a fixed-width terminal visual progress bar."""
    capped_ratio = min(max(ratio, 0.0), 10.0)
    filled = int(round((capped_ratio / 10.0) * width))
    unfilled = width - filled
    rating = scale_rating(ratio)
    return f"[{'█' * filled}{'░' * unfilled}]  {rating['grade']} {ratio:.1f}x"


def monetary_value(ratio: float, reference_usd: float = REFERENCE_USD) -> Dict[str, Any]:
    """Translates CER into business savings per $100 spent on raw token operations."""
    loci_usd = round(reference_usd / max(ratio, 0.01), 2)
    saved_usd = round(reference_usd - loci_usd, 2)
    saved_pct = round((saved_usd / reference_usd) * 100.0, 1)
    return {
        "baseline_usd": reference_usd,
        "loci_cost_usd": loci_usd,
        "saved_usd": saved_usd,
        "saved_pct": f"{saved_pct}%",
        "display": f"${reference_usd:.0f} raw → ${loci_usd:.2f} LOCI  (saved ${saved_usd:.2f} · {saved_pct}%)",
    }


def efficiency_report(
    hits: List[Dict[str, Any]],
    total_raw_entities_scanned: int,
    hierarchy_nodes: int = 0
) -> Dict[str, Any]:
    """Generates complete efficiency and CER report for context operations."""
    loci_cost = loci_token_cost(hits, hierarchy_nodes)
    baseline_cost = baseline_token_cost(total_raw_entities_scanned)
    cer = efficiency_ratio(loci_cost, baseline_cost)
    rating = scale_rating(cer)
    bar = scale_bar(cer)
    money = monetary_value(cer)

    num_hits = sum(1 for h in hits if h.get("entity_type") == "number")
    str_hits = len(hits) - num_hits

    return {
        "loci_tokens": loci_cost,
        "baseline_tokens": baseline_cost,
        "ratio": cer,
        "grade": rating["grade"],
        "emoji": rating["emoji"],
        "scale_bar": bar,
        "note": rating["note"],
        "monetary": money,
        "comparison": {
            "raw_entities_scanned": total_raw_entities_scanned,
            "hits_returned": len(hits),
            "number_hits": num_hits,
            "string_hits": str_hits,
            "number_weight": TOKEN_WEIGHTS["by_value_number"],
            "string_weight": TOKEN_WEIGHTS["by_value"],
            "standard_weight": TOKEN_WEIGHTS["full_scan"],
            "multiplier_vs_standard": round(TOKEN_WEIGHTS["full_scan"] / TOKEN_WEIGHTS["by_value_number"], 1)
        }
    }


def log_token_efficiency(
    conn: sqlite3.Connection,
    key_id: str,
    session_id: str,
    q_str: str,
    report: Dict[str, Any]
) -> None:
    """
    Persists audit entry into token_efficiency_log.
    Safe for concurrent async writes due to PRAGMA journal_mode=WAL.
    """
    q_hash = query_hash(q_str)
    conn.execute(
        """
        INSERT INTO token_efficiency_log (
            key_id, session_id, query_hash, raw_entities_scanned,
            hits_returned, loci_tokens, baseline_tokens, cer_ratio, grade
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            key_id,
            session_id,
            q_hash,
            report["comparison"]["raw_entities_scanned"],
            report["comparison"]["hits_returned"],
            report["loci_tokens"],
            report["baseline_tokens"],
            report["ratio"],
            report["grade"]
        )
    )
