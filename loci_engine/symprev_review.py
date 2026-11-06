#!/usr/bin/env python3
"""SYMPREV review: CARD budget on isymprev narrative, qsymprev values intact.

Caller spelling Symprev (S-Y-M-P-R-E-V) is accepted. Published text uses
SympPrev / symprev. ZIP audit Table 3 expands SymPrev as Symbolic Link
Preview / SymLink Preview. No separate paper titled "SimLink review
system" was found in the nine works.

Stream names that share a letter are not one type. In particular,
TD Commons 11089 SSympPrev is reflection-on-action, while the ZIP
registry's SSymPrev is Simulation. This module keeps those source
namespaces apart. Package theta_HOT 0.725 is not applied.

Injected narrative (isymprev) is bounded by CardRouter's category token
budget, the knob described for 10806's injection section. Exact qsymprev
rows keep quantity, unit, polarity, provenance, and validity fields.
A missing key returns not_found. A superseded or expired row is withheld,
not rewritten. Token counts are utf8_bytes_div_4, not a neural tokenizer.
A shorter packet is not called golden.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Optional

from loci_engine.card_router import CardRouter
from loci_engine.unified_core import DynamicTokenCoupledSnippetEngine


# Source-qualified names. Do not collapse rows that share a letter.
STREAMS = {
    "tdcommons:10806.isymprev": {
        "role": "heat_narrative",
        "sources": ["tdcommons:10806", "zenodo:10.5281/zenodo.21188425"],
    },
    "tdcommons:10806.qsymprev": {
        "role": "exact_typed_value_or_not_found",
        "sources": ["tdcommons:10806", "tdcommons:10843", "zenodo:10.5281/zenodo.21188425"],
    },
    "tdcommons:11089.MSympPrev": {
        "role": "mood_from_reconstruction_error",
        "sources": ["tdcommons:11089"],
    },
    "tdcommons:11089.SSympPrev": {
        "role": "reflection_on_action",
        "sources": ["tdcommons:11089", "tdcommons:11090"],
    },
    "zip_package.SSymPrev": {
        "role": "simulation",
        "sources": ["zip:symprev_registry"],
        "not_the_same_as": "tdcommons:11089.SSympPrev",
    },
    "tdcommons:11089.DSympPrev": {
        "role": "forecast_ensemble",
        "sources": ["tdcommons:11089", "tdcommons:11666"],
    },
    "zip_package.DSymPrev": {
        "role": "dream",
        "sources": ["zip:symprev_registry"],
        "not_the_same_as": "tdcommons:11089.DSympPrev",
    },
    "this_repo.dream_engine.DSymPrev": {
        "role": "quarantine_label_on_dream_pairs",
        "sources": ["loci_engine.dream_engine"],
        "not_the_same_as": "tdcommons:11089.DSympPrev",
    },
}

ALIASES = {
    "SYMPREV": "caller spelling for this review; not a tenth paper",
    "Symprev": "caller spelling for this review; not a tenth paper",
    "SympPrev": "spelling used in the nine papers",
    "SymLink Preview": "ZIP audit Table 3 expansion of SymPrev",
    "SimLink": "no separate titled paper found; not a module in this repository",
    "QSymPrev": "this repo's ethical_core.qsymprev; paper stream is qsymprev",
    "ISymPrev": "paper stream isymprev; not a second exact-fact bus",
    "isymprev": "tdcommons:10806.isymprev",
    "qsymprev": "tdcommons:10806.qsymprev",
}

TOKEN_ESTIMATE_METHOD = "utf8_bytes_div_4"


def estimate_tokens(text: str) -> Dict[str, Any]:
    size = len(text.encode("utf-8"))
    tokens = (size // 4) + (1 if size else 0)
    return {"method": TOKEN_ESTIMATE_METHOD, "bytes": size, "tokens": tokens, "model_tokenizer": False}


def current_qsymprev(facts: List[Dict[str, Any]], now: Optional[float] = None) -> Dict[str, Any]:
    """Keep the current typed row. Superseded and expired rows are withheld.

    Nothing in a withheld row is copied into the survivor. A later lookup
    that matches nothing returns not_found rather than a filled-in value.
    """
    superseded_ids = {fact.get("supersedes") for fact in facts if fact.get("supersedes")}
    live = []
    withheld = []
    for fact in facts:
        fact_id = fact.get("id") or fact.get("source_id")
        if fact_id in superseded_ids:
            withheld.append({"id": fact_id, "reason": "superseded"})
            continue
        until = fact.get("valid_until")
        if until is not None and now is not None and float(now) >= float(until):
            withheld.append({"id": fact_id, "reason": "expired"})
            continue
        live.append(dict(fact))
    return {"stream": "tdcommons:10806.qsymprev", "current": live, "withheld": withheld}


def lookup_qsymprev(facts: List[Dict[str, Any]], key: str, now: Optional[float] = None) -> Dict[str, Any]:
    """Mode B: one current value, or not_found. Ambiguous keys are not averaged."""
    current = current_qsymprev(facts, now)["current"]
    matches = [fact for fact in current if fact.get("key") == key or fact.get("name") == key]
    if not matches:
        return {"status": "not_found", "key": key, "value": None, "unit": None, "stream": "tdcommons:10806.qsymprev"}
    if len(matches) > 1:
        return {"status": "ambiguous", "key": key, "value": None, "unit": None, "count": len(matches)}
    fact = matches[0]
    return {
        "status": "value",
        "key": key,
        "value": fact.get("quantity", fact.get("value")),
        "unit": fact.get("unit"),
        "polarity": fact.get("polarity"),
        "valid_from": fact.get("valid_from"),
        "valid_until": fact.get("valid_until"),
        "source_id": fact.get("source_id"),
        "stream": "tdcommons:10806.qsymprev",
    }


def _window(text: str, query: str, max_bytes: int) -> Optional[str]:
    """A source window, not a paraphrase. None when even a short window cannot fit."""
    if max_bytes < 16:
        return None
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    lower = text.lower()
    byte_at = 0
    for token in re.findall(r"[a-z0-9]{3,}", query.lower()):
        at = lower.find(token)
        if at >= 0:
            byte_at = len(text[:at].encode("utf-8"))
            break
    start = max(0, byte_at - max_bytes // 5)
    chunk = raw[start:start + max_bytes]
    excerpt = chunk.decode("utf-8", errors="ignore").strip()
    return excerpt or None


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
                "stream": "tdcommons:10806.isymprev",
                "source_id": item.get("source_id") or item_id,
                "heat": item.get("heat"),
                "content_sha256": content_sha,
                "token_estimate": estimate_tokens(text)["tokens"],
                "_text": text,
            }
        )

    qbus = current_qsymprev(exact_facts)
    injected_facts = qbus["current"]
    for row in qbus["withheld"]:
        dropped.append(row)
    # The category budget counts the whole answer packet, including ids and
    # the exact-fact JSON. A later wrapper must not be allowed to report a
    # larger "selected" count than this budget.
    skeleton = {"isymprev": [], "qsymprev": injected_facts}
    exact_tokens = estimate_tokens(json.dumps(injected_facts, sort_keys=True))["tokens"]
    wrapper_tokens = estimate_tokens(json.dumps(skeleton, sort_keys=True))["tokens"] - exact_tokens
    kept: List[Dict[str, Any]] = []
    reexpand_required: List[str] = []
    if exact_tokens > budget:
        status = "budget_exceeded_exact_facts_retained"
        answer_ready = False
        rendered_obj = skeleton
    else:
        used = estimate_tokens(json.dumps(skeleton, sort_keys=True))["tokens"]
        for symbol in symbols:
            source_text = symbol.pop("_text")
            remaining_tokens = budget - used
            snippet = DynamicTokenCoupledSnippetEngine.resolve_snippet_budget(
                float(symbol.get("heat") or 0.5),
                0.0,
                tokens_already_consumed=min(used, DynamicTokenCoupledSnippetEngine.MILLER_TOKEN_CEILING),
            )
            max_bytes = min(int(snippet["allocated_bytes"]), max(0, remaining_tokens) * 4)
            excerpt = _window(source_text, query, max_bytes)
            if excerpt is None:
                reexpand_required.append(symbol["source_id"])
                dropped.append({"id": symbol["id"], "reason": "reexpansion_required"})
                continue
            candidate = dict(symbol)
            candidate["excerpt"] = excerpt
            candidate["excerpt_is_full_source"] = excerpt == source_text
            candidate["token_estimate"] = estimate_tokens(excerpt)["tokens"]
            trial = {"isymprev": kept + [candidate], "qsymprev": injected_facts}
            trial_tokens = estimate_tokens(json.dumps(trial, sort_keys=True))["tokens"]
            if trial_tokens > budget:
                reexpand_required.append(symbol["source_id"])
                dropped.append({"id": symbol["id"], "reason": "reexpansion_required"})
                continue
            kept.append(candidate)
            used = trial_tokens
        rendered_obj = {"isymprev": kept, "qsymprev": injected_facts}
        if kept:
            status = "ok" if not reexpand_required else "partial_excerpt_exact_facts_retained"
            answer_ready = True
        elif reexpand_required or symbols:
            status = "reexpansion_required"
            answer_ready = False
        else:
            status = "ok"
            answer_ready = bool(injected_facts) or not symbols
    rendered = json.dumps(rendered_obj, sort_keys=True)
    packet_tokens = estimate_tokens(rendered)["tokens"]
    excerpt_tokens = sum(estimate_tokens(row.get("excerpt") or "")["tokens"] for row in kept)
    refs_only = (not kept) and (not injected_facts) and (not answer_ready)
    return {
        "interface": "SYMPREV",
        "called_golden": False,
        "optimized": False,
        "semantic_validation": False,
        "neural_embeddings": False,
        "theta_hot_0_725_applied": False,
        "token_estimate_method": TOKEN_ESTIMATE_METHOD,
        "snippet_engine": "DynamicTokenCoupledSnippetEngine",
        "archetype": card["archetype"],
        "depth_k": card["depth_k"],
        "token_budget": budget,
        "symbols": kept,
        "isymprev": kept,
        "exact_facts": injected_facts,
        "qsymprev": injected_facts,
        "qsymprev_withheld": qbus["withheld"],
        "exact_facts_truncated": False,
        "dropped": dropped,
        "reexpand_source_ids": reexpand_required,
        "status": status,
        "answer_ready": answer_ready,
        "refs_only": refs_only,
        "policy": policy,
        "packet_tokens": packet_tokens,
        "exact_fact_tokens": exact_tokens,
        "wrapper_tokens": max(0, wrapper_tokens),
        "excerpt_tokens": excerpt_tokens,
        "reexpansion_tokens": excerpt_tokens,
        "selected_token_estimate": estimate_tokens(rendered),
        "budget_respected_when_facts_fit": exact_tokens > budget or packet_tokens <= budget,
        "streams": STREAMS,
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
    total = selected["tokens"] + review_overhead["tokens"]
    answer_ready = bool(packet.get("answer_ready"))
    grew = total > base_tokens
    # A smaller byte count is not a saving when the packet is not an answer,
    # and a wrapper that grows a short source is not an optimization.
    optimized = answer_ready and not packet.get("refs_only") and total < base_tokens
    return {
        "baseline": baseline,
        "selected": selected,
        "packet_tokens": packet.get("packet_tokens"),
        "wrapper_tokens": packet.get("wrapper_tokens"),
        "exact_fact_tokens": packet.get("exact_fact_tokens"),
        "excerpt_tokens": packet.get("excerpt_tokens"),
        "reexpansion_tokens": packet.get("reexpansion_tokens"),
        "review_overhead": review_overhead,
        "total_tokens": total,
        "reduction_ratio_selected_over_baseline": selected["tokens"] / base_tokens,
        "answer_ready": answer_ready,
        "refs_only": bool(packet.get("refs_only")),
        "optimized": optimized,
        "grew": grew,
        "bypass": grew,
        "model_invoked": False,
        "api_usage": None,
        "money_saved": None,
        "byte_estimate_only": True,
        "quality_guaranteed": False,
        "exact_facts_truncated": packet["exact_facts_truncated"],
        "budget_respected_when_facts_fit": packet.get("budget_respected_when_facts_fit"),
    }
