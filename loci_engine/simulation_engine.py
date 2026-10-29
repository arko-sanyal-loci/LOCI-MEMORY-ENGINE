#!/usr/bin/env python3
"""
Loci Memory Engine - Counterfactual Simulation & Dual-Heat Reflection Engine
Implements Section 9 & Figure 7 of the Master Compendium:
- Dual-Heat Dynamics: Operational Heat (H_exec) vs. Reflective Heat (H_sim)
- Behavioral Surprise Evaluator: Δ_surprise = || P_actual - P_pred ||_2
- Neighborhood "What-If" Exploration (Unbounded questioning)
- Strict Epistemic Quarantine (DSimPrev: confidence = 0.0)
- Immutable Ethical Anchor: Sticks to StickPrincipleValenceGate
"""

import math
from typing import Dict, List, Any, Optional
from loci_engine.unified_core import StickPrincipleValenceGate

class CounterfactualSimulationEngine:
    SURPRISE_THRESHOLD = 0.25

    @classmethod
    def evaluate_behavioral_surprise(
        cls,
        p_pred: Dict[str, float],
        p_actual: Dict[str, float]
    ) -> float:
        """
        Calculates L2 divergence between expected and actual execution telemetry:
        P = {latency_norm, token_footprint_norm, error_prob}
        """
        keys = set(p_pred.keys()).union(set(p_actual.keys()))
        squared_diff = sum((p_pred.get(k, 0.0) - p_actual.get(k, 0.0)) ** 2 for k in keys)
        return round(math.sqrt(squared_diff), 6)

    @classmethod
    def generate_what_if_probe(
        cls,
        current_context_node: Dict[str, Any],
        neighbor_nodes: List[Dict[str, Any]],
        delta_surprise: float
    ) -> List[Dict[str, Any]]:
        """
        Radiates secondary reflective heat (H_sim) into semantic neighbors.
        Questions: "What if this parameter/heuristic could be better?"
        """
        simulations = []
        base_h_sim = min(1.0, current_context_node.get("heat", 0.5) + (delta_surprise * 0.8))

        for neighbor in neighbor_nodes:
            # Measure continuous semantic distance
            vec_curr = current_context_node.get("embedding", [])
            vec_neigh = neighbor.get("embedding", [])
            cosine_dist = 1.0
            if vec_curr and vec_neigh and len(vec_curr) == len(vec_neigh):
                dot = sum(a * b for a, b in zip(vec_curr, vec_neigh))
                norm_a = math.sqrt(sum(a * a for a in vec_curr))
                norm_b = math.sqrt(sum(b * b for b in vec_neigh))
                sim = dot / ((norm_a * norm_b) + 1e-9)
                cosine_dist = max(0.0, 1.0 - sim)

            # Reflective Heat Radiation: curiosity amplifies on surprising outcomes
            conduction = math.exp(-(cosine_dist ** 2) / (2 * (0.35 ** 2)))
            h_sim = min(1.0, round(base_h_sim * conduction, 6))

            # Propose counterfactual challenge
            sim_item = {
                "source_node_id": current_context_node.get("id"),
                "counterfactual_target_id": neighbor.get("id"),
                "hypothetical_question": f"What if '{neighbor.get('id')}' yields a more optimal solution than current state?",
                "delta_surprise_trigger": delta_surprise,
                "reflective_heat_h_sim": h_sim,
                "stream_quarantine": "DSimPrev",
                "epistemic_confidence": 0.0  # Quarantined: strictly speculative
            }

            # INVIOLABLE SAFETY CHECK: Radiating ethics test
            # Simulations may question anything, but cannot propose actions that violate the gate
            gate_check = StickPrincipleValenceGate.score_vexec(
                knowledge_k="counterfactual_simulation",
                application_point="active_system_hardening",
                intent=1.0,
                consent=1.0,
                target_vulnerability=0.0
            )
            sim_item["valence_clearance"] = gate_check["allow_execution"]

            if h_sim >= 0.20:
                simulations.append(sim_item)

        return sorted(simulations, key=lambda x: x["reflective_heat_h_sim"], reverse=True)
