#!/usr/bin/env python3
"""
Loci Memory Engine - Thermodynamic Gradient & Semantic Heat Conduction
Replaces discrete graph hops with continuous Euclidean/Cosine thermal dissipation.
Defines explicit tiers: HOT (VRAM/Prompt), MILD (RAM/SLP), COLD (NVMe/Disk).
Zero external dependencies beyond standard library math.
"""

import math
from typing import Dict, List, Any

class ThermodynamicNeighborhoodEngine:
    TIER_HOT_THRESHOLD = 0.70
    TIER_MILD_THRESHOLD = 0.25
    DEFAULT_SIGMA = 0.32  # Spatial dispersion radius

    @classmethod
    def classify_tier(cls, temperature: float) -> str:
        if temperature >= cls.TIER_HOT_THRESHOLD:
            return "HOT"
        elif temperature >= cls.TIER_MILD_THRESHOLD:
            return "MILD"
        return "COLD"

    @classmethod
    def diffuse_heat_gradient(
        cls,
        active_nodes: List[Dict[str, Any]],
        candidate_nodes: List[Dict[str, Any]],
        sigma: float = DEFAULT_SIGMA
    ) -> List[Dict[str, Any]]:
        """
        Calculates continuous temperature propagation from active nodes to candidates.
        No discrete hops: heat dissipates continuously over cosine distance.
        """
        results = []
        for cand in candidate_nodes:
            cand_vec = cand.get("embedding", [])
            base_temp = cand.get("heat", 0.0)
            radiated_heat = 0.0

            if cand_vec:
                for act in active_nodes:
                    act_vec = act.get("embedding", [])
                    act_temp = act.get("heat", 1.0)
                    if act_vec and len(act_vec) == len(cand_vec):
                        dot = sum(a * b for a, b in zip(act_vec, cand_vec))
                        norm_a = math.sqrt(sum(a * a for a in act_vec))
                        norm_b = math.sqrt(sum(b * b for b in cand_vec))
                        cosine_dist = max(0.0, 1.0 - (dot / ((norm_a * norm_b) + 1e-9)))

                        # Gaussian heat conduction
                        conduction = math.exp(-(cosine_dist ** 2) / (2 * (sigma ** 2)))
                        rel_weight = cand.get("rel_weight", 1.0)
                        radiated_heat += act_temp * conduction * rel_weight

            effective_temp = min(1.0, base_temp + radiated_heat)
            tier = cls.classify_tier(effective_temp)

            updated = dict(cand)
            updated["effective_heat"] = round(effective_temp, 6)
            updated["thermodynamic_tier"] = tier
            results.append(updated)

        return sorted(results, key=lambda x: x["effective_heat"], reverse=True)
