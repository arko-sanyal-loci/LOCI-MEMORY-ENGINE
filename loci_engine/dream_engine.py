#!/usr/bin/env python3
"""
Loci Memory Engine - Geodesic Imagination Engine (DSymPrev Stream)
Compendium Citation: Figure 5 (Riemannian Geodesic Dream Score)
Formula: dream_score = (1 - cos(A, B)) * heat_A * heat_B
"""

import math
from typing import Dict, List, Any

class GeodesicDreamEngine:
    MIN_HEAT_ANCHOR = 0.70   # Both concepts must be verified truths (Hot/Upper-Mild)
    MIN_DREAM_SCORE = 0.35

    @staticmethod
    def cosine_similarity(v1: List[float], v2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(v1, v2))
        norm1 = math.sqrt(sum(a * a for a in v1))
        norm2 = math.sqrt(sum(b * b for b in v2))
        if norm1 == 0.0 or norm2 == 0.0:
            return 0.0
        return max(-1.0, min(1.0, dot / (norm1 * norm2)))

    @classmethod
    def evaluate_dream_pair(cls, node_a: Dict[str, Any], node_b: Dict[str, Any]) -> Dict[str, Any]:
        heat_a = float(node_a.get("heat", 0.0))
        heat_b = float(node_b.get("heat", 0.0))
        vec_a = node_a.get("embedding", [])
        vec_b = node_b.get("embedding", [])

        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return {"dream_score": 0.0, "is_viable": False}

        cos_sim = cls.cosine_similarity(vec_a, vec_b)
        # Semantic Geodesic Distance: maximizes anti-similarity across the manifold
        geodesic_dist = 1.0 - cos_sim

        # Joint Confidence Anchor: heat_a * heat_b
        dream_score = geodesic_dist * heat_a * heat_b
        is_viable = (heat_a >= cls.MIN_HEAT_ANCHOR and 
                     heat_b >= cls.MIN_HEAT_ANCHOR and 
                     dream_score >= cls.MIN_DREAM_SCORE)

        return {
            "node_a_id": node_a.get("id"),
            "node_b_id": node_b.get("id"),
            "geodesic_distance": round(geodesic_dist, 6),
            "joint_heat": round(heat_a * heat_b, 6),
            "dream_score": round(dream_score, 6),
            "is_viable": is_viable,
            "stream_quarantine": "DSymPrev",
            "epistemic_confidence": 0.0  # Invariant: speculative thoughts cannot self-promote
        }
