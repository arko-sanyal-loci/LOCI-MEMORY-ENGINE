"""
LOCI & TRS Empirical Threshold Calibration Harness
Objective:
Run systematic parameter sweeps on theta_HOT (0.60 to 0.95) and alpha floor (0.005 vs 0.050)
to measure concrete trade-offs:
1. Working set item count & token footprint (Miller's Law <= 560 tokens, 7 +/- 2 items)
2. Precision vs Recall on multi-turn retrieval
3. Noise leakage (distractor admission rate)
4. Creative resonance detection (spark ignition without context flooding)
"""

import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

@dataclass
class EntityNode:
    id: str
    is_target: bool         # Ground truth relevant to active goal
    is_distractor: bool     # Background noise / unrelated
    is_creative_spark: bool # Cross-domain latent innovation
    heat: float = 0.05
    relevance: float = 0.0

def generate_evaluation_workload(alpha: float, n_distractors: int = 40) -> Dict[str, EntityNode]:
    """Generates a realistic multi-turn context graph."""
    nodes = {}
    # 5 Target entities (Core task)
    for i in range(5):
        nodes[f"target_{i}"] = EntityNode(
            id=f"target_{i}", is_target=True, is_distractor=False, is_creative_spark=False,
            heat=0.72 + (i * 0.05), relevance=0.92 + (i * 0.015)
        )
    # 2 Latent creative spark nodes (Cross-domain collision)
    nodes["spark_core"] = EntityNode(
        id="spark_core", is_target=False, is_distractor=False, is_creative_spark=True,
        heat=0.55, relevance=0.78
    )
    nodes["spark_peripheral"] = EntityNode(
        id="spark_peripheral", is_target=False, is_distractor=False, is_creative_spark=True,
        heat=0.48, relevance=0.75
    )
    # N distractors resting near alpha floor with slight fluctuations
    for i in range(n_distractors):
        noise_heat = min(0.65, alpha + random.betavariate(1.5, 8.0) * 0.45)
        nodes[f"noise_{i}"] = EntityNode(
            id=f"noise_{i}", is_target=False, is_distractor=True, is_creative_spark=False,
            heat=noise_heat, relevance=random.uniform(0.10, 0.55)
        )
    return nodes

def evaluate_threshold(theta_hot: float, alpha: float, trials: int = 100) -> Dict[str, float]:
    total_admitted_items = 0
    total_tokens = 0
    target_hits = 0
    distractor_leaks = 0
    spark_detected = 0
    
    # Approx 45 tokens per admitted entity summary under SymLinkPrev expansion
    TOKENS_PER_ITEM = 45

    random.seed(42)  # Deterministic repeatability

    for _ in range(trials):
        workload = generate_evaluation_workload(alpha=alpha)
        admitted = []

        # Check resonance between spark nodes
        spark_co_act = workload["spark_core"].heat * workload["spark_peripheral"].heat * 2.8
        spark_ignited = spark_co_act > 0.40
        if spark_ignited:
            workload["spark_core"].heat = min(0.98, workload["spark_core"].heat + 0.35)
            workload["spark_peripheral"].heat = min(0.95, workload["spark_peripheral"].heat + 0.30)

        for eid, node in workload.items():
            if node.heat >= theta_hot:
                admitted.append(node)

        total_admitted_items += len(admitted)
        total_tokens += len(admitted) * TOKENS_PER_ITEM

        for node in admitted:
            if node.is_target:
                target_hits += 1
            elif node.is_distractor:
                distractor_leaks += 1
            elif node.is_creative_spark:
                spark_detected += 1

    mean_items = total_admitted_items / trials
    mean_tokens = total_tokens / trials
    
    # 5 targets * trials total
    recall = target_hits / (5 * trials)
    # precision = target_hits / total_admitted (if any admitted)
    precision = target_hits / total_admitted_items if total_admitted_items > 0 else 1.0
    noise_rate = distractor_leaks / total_admitted_items if total_admitted_items > 0 else 0.0
    spark_recall = spark_detected / (2 * trials)

    return {
        "theta_hot": theta_hot,
        "alpha": alpha,
        "mean_items": round(mean_items, 2),
        "mean_tokens": round(mean_tokens, 1),
        "precision": round(precision * 100, 1),
        "recall": round(recall * 100, 1),
        "noise_rate": round(noise_rate * 100, 1),
        "spark_recall": round(spark_recall * 100, 1),
        "millers_law_pass": 5 <= mean_items <= 9 and mean_tokens <= 560
    }

def run_parameter_sweeps():
    print("=" * 90)
    print("LOCI / TRS EMPIRICAL THRESHOLD SWEEP: EVALUATING SOURCE OF TRUTH")
    print("=" * 90)
    print(f"{'Theta_HOT':<10} | {'Alpha':<6} | {'Items':<7} | {'Tokens':<7} | {'Precision':<10} | {'Recall':<8} | {'Noise Leak':<11} | {'Spark Catch':<11} | {'Status'}")
    print("-" * 90)

    # Test legacy floor 0.005 vs proposed 0.050 across candidate thresholds
    thresholds = [0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    
    for alpha in [0.005, 0.050]:
        print(f"\n[Floor alpha = {alpha:.3f}]")
        for th in thresholds:
            res = evaluate_threshold(theta_hot=th, alpha=alpha, trials=200)
            status = "OPTIMAL" if res["millers_law_pass"] and res["precision"] > 75 and res["recall"] > 70 else "OFF-TARGET"
            print(f"{res['theta_hot']:<10.2f} | {res['alpha']:<6.3f} | {res['mean_items']:<7.1f} | {res['mean_tokens']:<7.0f} | {res['precision']:<9.1f}% | {res['recall']:<7.1f}% | {res['noise_rate']:<10.1f}% | {res['spark_recall']:<10.1f}% | {status}")

    print("\n" + "=" * 90)

if __name__ == "__main__":
    run_parameter_sweeps()
