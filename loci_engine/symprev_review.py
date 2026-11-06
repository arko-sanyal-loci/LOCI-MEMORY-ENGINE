#!/usr/bin/env python3
"""SYMPREV review: category budget over symbols, exact facts kept whole.

Caller spelling SYMPREV (also written Symprev) is the interface name for
this review. It is not a new paper and it is not a "Sim" module.

Names already in this repository, and the only mappings used here:

- QSymPrev / ISymPrev: quantified-fact caution in ethical_core.qsymprev
  and FactSymPrevEngine. Exact quantities are not guessed or clipped.
- DSymPrev: dream-stream quarantine label in dream_engine. Simulated
  scores stay candidates.
- SymLinkPrevNode: 20-byte locator pack in slp_arena. This review does
  not pack source ids into those 8-byte locators, because that would
  cut the id off.
- isymprev / qsymprev tables: present in loci-memory-engine-1, not in
  this checkout's schema.

No module named SimLink was found. A parallel source check may still
locate that wording. This file does not invent that paper.

Token counts use UTF-8 byte length divided by 4, the same estimate
DynamicTokenCoupledSnippetEngine already uses. That is not a model
tokenizer, and no model was called. A shorter packet is not called golden.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List, Optional

from loci_engine.card_router import CardRouter


ALIASES = {
    "SYMPREV": "loci_engine.symprev_review.review_context",
    "Symprev": "loci_engine.symprev_review.review_context",
    "SympPrev": "spelling variant; same review interface, not a separate module",
    "QSymPrev": "loci_engine.ethical_core.qsymprev and loci_engine.sanitizer.FactSymPrevEngine",
    "ISymPrev": "informational counterpart named beside QSymPrev in ethical_core",
    "DSymPrev": "loci_engine.dream_engine quarantine label",
    "SymLinkPrev": "loci_engine.slp_arena.SymLinkPrevNode",
    "SymLink": "loci_engine.slp_arena.SymLinkPrevNode",
    "SimLink": "not a module in this repository; no SimLink paper is claimed",
    "isymprev": "table in loci-memory-engine-1, not created by this checkout",
    "qsymprev": "function qsymprev in this repo; table only in loci-memory-engine-1",
}

TOKEN_ESTIMATE_METHOD = "utf8_bytes_div_4"


def estimate_tokens(text: str) -> Dict[str, Any]:
    size = len(text.encode("utf-8"))
    tokens = (size // 4) + (1 if size else 0)
    return {"method": TOKEN_ESTIMATE_METHOD, "bytes": size, "tokens": tokens, "model_tokenizer": False}


def review_context(
    *,
    query: str,
    items: List[Dict[str, Any]],
    exact_facts: List[Dict[str, Any]],
    policy: Dict[str, Any],
    token_budget: Optional[int] = None,
) -> Dict[str, Any]:
    """Return symbols under the CARD budget. Exact facts are not clipped.

    If the exact-fact bus alone exceeds the budget, symbols are omitted and
    status is budget_exceeded_exact_facts_retained. The facts stay complete.
    Contradictory or unsupported items are listed as dropped, not merged.
    """
    card = CardRouter.execute_card_retrieval(query, items)
    budget = int(token_budget if token_budget is not None else card["token_budget"])
    seen = set()
    symbols: List[Dict[str, Any]] = []
    dropped: List[Dict[str, Any]] = []
    for item in card["selected_items"]:
        item_id = str(item.get("id"))
        if item.get("contradictory"):
            dropped.append({"id": item_id, "reason": "contradictory"})
            continue
        if item.get("support") is False:
            dropped.append({"id": item_id, "reason": "unsupported"})
            continue
        text = str(item.get("statement") or item.get("text") or "")
        content_sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        if content_sha in seen:
            dropped.append({"id": item_id, "reason": "redundant"})
            continue
        seen.add(content_sha)
        symbols.append(
            {
                "id": item_id,
                "source_id": item.get("source_id") or item_id,
                "heat": item.get("heat"),
                "content_sha256": content_sha,
                "token_estimate": estimate_tokens(text)["tokens"],
            }
        )

    exact_render = json.dumps(exact_facts, sort_keys=True)
    exact_tokens = estimate_tokens(exact_render)["tokens"]
    kept: List[Dict[str, Any]] = []
    used = exact_tokens
    reexpand_required = []
    for symbol in symbols:
        cost = int(symbol["token_estimate"])
        if used + cost > budget:
            reexpand_required.append(symbol["source_id"])
            dropped.append({"id": symbol["id"], "reason": "over_category_budget"})
            continue
        kept.append(symbol)
        used += cost
    status = "ok"
    if exact_tokens > budget:
        kept = []
        reexpand_required = [symbol["source_id"] for symbol in symbols]
        status = "budget_exceeded_exact_facts_retained"
        used = exact_tokens
    elif reexpand_required:
        status = "partial_symbols_exact_facts_retained"

    rendered = json.dumps({"symbols": kept, "exact_facts": exact_facts}, sort_keys=True)
    return {
        "interface": "SYMPREV",
        "called_golden": False,
        "semantic_validation": False,
        "neural_embeddings": False,
        "token_estimate_method": TOKEN_ESTIMATE_METHOD,
        "archetype": card["archetype"],
        "depth_k": card["depth_k"],
        "token_budget": budget,
        "symbols": kept,
        "exact_facts": list(exact_facts),
        "exact_facts_truncated": False,
        "dropped": dropped,
        "reexpand_source_ids": reexpand_required,
        "status": status,
        "policy": policy,
        "selected_token_estimate": estimate_tokens(rendered),
        "aliases": ALIASES,
    }


def reexpand(packet: Dict[str, Any], source_id: str, sources: Dict[str, str]) -> Dict[str, Any]:
    """Return the stored source text, or abstain when it is absent."""
    if source_id not in sources:
        return {
            "status": "missing_support",
            "source_id": source_id,
            "text": None,
            "abstained": True,
        }
    text = sources[source_id]
    return {
        "status": "reexpanded",
        "source_id": source_id,
        "text": text,
        "token_estimate": estimate_tokens(text),
        "abstained": False,
    }


def measure_context(full_text: str, packet: Dict[str, Any]) -> Dict[str, Any]:
    """Compare full-context estimate with the reviewed packet.

    Review overhead is counted separately. No API price is claimed.
    """
    baseline = estimate_tokens(full_text)
    selected = packet["selected_token_estimate"]
    review_overhead = estimate_tokens(json.dumps({
        "dropped": packet["dropped"],
        "status": packet["status"],
        "archetype": packet["archetype"],
    }))
    base_tokens = baseline["tokens"] or 1
    return {
        "baseline": baseline,
        "selected": selected,
        "review_overhead": review_overhead,
        "reduction_ratio_selected_over_baseline": selected["tokens"] / base_tokens,
        "model_invoked": False,
        "api_usage": None,
        "money_saved": None,
        "quality_guaranteed": False,
        "exact_facts_truncated": packet["exact_facts_truncated"],
    }
