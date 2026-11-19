"""
Fine-Grained Threshold & Noise Stress Test
Evaluating:
- Clean context (normal dialogue)
- Noisy context (high background clutter, 100 distractor entities)
- High-drift context (adversarial semantic drift)
"""

import random
from threshold_sweep_experiment import evaluate_threshold

def run_fine_grained_sweep():
    print("=" * 100)
    print("FINE-GRAINED CALIBRATION: FINDING THE EMPIRICAL SWEET SPOT FOR THETA_HOT")
    print("=" * 100)
    print(f"{'Theta_HOT':<10} | {'Items':<7} | {'Tokens':<8} | {'Precision':<11} | {'Recall':<8} | {'Noise Leak':<11} | {'Spark Catch':<12} | {'Miller Compliance'}")
    print("-" * 100)

    # Sweep from 0.65 to 0.85 in 0.025 increments with alpha = 0.050
    candidate_thresholds = [0.650, 0.675, 0.700, 0.725, 0.750, 0.775, 0.800, 0.825, 0.850]
    
    for th in candidate_thresholds:
        res = evaluate_threshold(theta_hot=th, alpha=0.050, trials=300)
        miller_flag = "PASS [7 +/- 2]" if 5.0 <= res["mean_items"] <= 9.0 and res["mean_tokens"] <= 560 else "FAIL"
        print(f"{res['theta_hot']:<10.3f} | {res['mean_items']:<7.1f} | {res['mean_tokens']:<8.0f} | {res['precision']:<10.1f}% | {res['recall']:<7.1f}% | {res['noise_rate']:<10.1f}% | {res['spark_recall']:<11.1f}% | {miller_flag}")

    print("=" * 100)

if __name__ == "__main__":
    run_fine_grained_sweep()
