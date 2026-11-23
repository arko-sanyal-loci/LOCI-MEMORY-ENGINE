#!/usr/bin/env python3
"""
Loci Memory Engine - Category-Adaptive Recall Depth (CARD) Engine
Implements the 4 core archetypes from LongMemEval-500:
1. Information Extraction (K=5, heat-descending)
2. Knowledge Update (K=3, recency tiebreak + canonical deduplication)
3. Multi-Session Reasoning (K=10, continuous neighborhood gradient)
4. Temporal Reasoning (K=7, timestamp chronological ordering)
"""

import math
from typing import Dict, List, Any, Mapping, Optional, Sequence

class CardRouter:
    ARCHETYPE_CONFIGS = {
        "information_extraction": {
            "depth_k": 5,
            "strategy": "heat_descending",
            "max_tokens": 180,
            "min_confidence": 0.50
        },
        "knowledge_update": {
            "depth_k": 3,
            "strategy": "recency_tiebreak",
            "max_tokens": 120,
            "min_confidence": 0.65
        },
        "multi_session_reasoning": {
            "depth_k": 10,
            "strategy": "gradient_conduction",
            "max_tokens": 450,
            "min_confidence": 0.40
        },
        "temporal_reasoning": {
            "depth_k": 7,
            "strategy": "temporal_ordered",
            "max_tokens": 280,
            "min_confidence": 0.45
        }
    }

    @classmethod
    def classify_archetype(cls, query: str) -> str:
        q = query.lower()
        if any(w in q for w in ["update", "changed", "now", "latest", "current", "supersede", "revision"]):
            return "knowledge_update"
        elif any(w in q for w in ["when", "timeline", "history", "before", "after", "earlier", "since"]):
            return "temporal_reasoning"
        elif any(w in q for w in ["why", "how did", "connect", "across", "relationship", "synthesize", "root cause"]):
            return "multi_session_reasoning"
        return "information_extraction"

    @classmethod
    def execute_card_retrieval(
        cls,
        query: str,
        candidates: List[Dict[str, Any]],
        active_embedding: Optional[List[float]] = None,
        sigma: float = 0.32,
        category_hint: Optional[str] = None,
        stream_context: Optional[Sequence[Mapping[str, Any]]] = None,
        tiebreaker_context: Optional[Mapping[str, float]] = None,
    ) -> Dict[str, Any]:
        archetype = category_hint if category_hint in cls.ARCHETYPE_CONFIGS else cls.classify_archetype(query)
        cfg = cls.ARCHETYPE_CONFIGS[archetype]
        depth_k = cfg["depth_k"]
        stream_context = stream_context or ()
        tiebreaker_context = tiebreaker_context or {}

        stream_scores: Dict[str, float] = {}
        for context in stream_context:
            item_id = context.get("id")
            if not item_id:
                continue
            try:
                score = max(0.0, min(1.0, float(context.get("score", 0.0))))
                hop = max(1, int(context.get("hop", 1)))
            except (TypeError, ValueError):
                continue
            stream_scores[item_id] = max(
                stream_scores.get(item_id, 0.0),
                score * (0.5 if hop == 1 else 0.25 if hop == 2 else 0.125),
            )

        # 1. Calculate continuous thermal gradient if semantic vector is present
        processed_pool = []
        for cand in candidates:
            item = dict(cand)
            base_temp = item.get("heat", 0.0)
            radiated_heat = 0.0

            cand_vec = item.get("embedding", [])
            if active_embedding and cand_vec and len(cand_vec) == len(active_embedding):
                dot = sum(a * b for a, b in zip(active_embedding, cand_vec))
                norm_a = math.sqrt(sum(a * a for a in active_embedding))
                norm_b = math.sqrt(sum(b * b for b in cand_vec))
                cosine_dist = max(0.0, 1.0 - (dot / ((norm_a * norm_b) + 1e-9)))

                # Continuous spatial dispersion
                conduction = math.exp(-(cosine_dist ** 2) / (2 * (sigma ** 2)))
                rel_weight = item.get("rel_weight", 1.0)
                radiated_heat = conduction * rel_weight * 0.85

            item["effective_heat"] = min(1.0, round(base_temp + radiated_heat, 6))
            item["stream_score"] = round(min(1.0, stream_scores.get(item.get("id"), 0.0)), 6)
            try:
                tie_score = float(tiebreaker_context.get(item.get("id"), 0.0))
            except (TypeError, ValueError):
                tie_score = 0.0
            item["tiebreaker_score"] = round(max(-1.0, min(1.0, tie_score)), 6)
            processed_pool.append(item)

        def rank_with_bounded_context(pool: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            """Use context only to resolve close heat scores, never hot/cold flips."""
            ranked = sorted(
                pool,
                key=lambda x: (x["effective_heat"], x.get("timestamp", 0), x.get("id", "")),
                reverse=True,
            )
            for index in range(len(ranked) - 1):
                current = ranked[index]
                following = ranked[index + 1]
                if current["effective_heat"] - following["effective_heat"] > 0.05:
                    continue
                current_context = current["stream_score"] + 0.05 * current["tiebreaker_score"]
                following_context = following["stream_score"] + 0.05 * following["tiebreaker_score"]
                if following_context > current_context:
                    ranked[index], ranked[index + 1] = following, current
            return ranked

        # 2. Apply archetype-specific ranking & filtering
        if cfg["strategy"] == "recency_tiebreak":
            # Sort by heat, break ties by timestamp
            sorted_pool = rank_with_bounded_context(processed_pool)
            # Retain only the latest valid version per entity_id
            seen_entities = set()
            selected = []
            for item in sorted_pool:
                entity = item.get("entity_id")
                if entity:
                    if entity not in seen_entities:
                        seen_entities.add(entity)
                        selected.append(item)
                else:
                    selected.append(item)
                if len(selected) >= depth_k:
                    break

        elif cfg["strategy"] == "temporal_ordered":
            # Select top-K hottest, then sort chronologically
            top_k_pool = rank_with_bounded_context(processed_pool)[:depth_k]
            selected = sorted(top_k_pool, key=lambda x: x.get("timestamp", 0))

        else:
            # Standard heat-descending or gradient conduction
            selected = rank_with_bounded_context(processed_pool)[:depth_k]

        selected = [item for item in selected if item["effective_heat"] >= cfg["min_confidence"]]

        return {
            "query": query,
            "archetype": archetype,
            "depth_k": depth_k,
            "token_budget": cfg["max_tokens"],
            "category_hint": category_hint,
            "selected_items": selected
        }
