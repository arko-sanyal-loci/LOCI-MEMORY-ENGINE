# ADR 0001 — HOT Tier Admission Threshold: θ_HOT = 0.70

**Status:** Accepted  
**Date:** 2026-11-19  
**Author:** Arko Sanyal (Billo Tech), documented by Claude Sonnet 4.6  

---

## Context

`loci_engine/heat.py` historically defined two thresholds:

| Symbol | Old value | Used where |
|---|---|---|
| `VRAM_ADMISSION_THRESHOLD` | `0.700` | Declared in heat.py but **never read** by storage, thermal_gradient, or retrieval code |
| *(implicit in docstring)* | `0.800` | Storage `StorageEngine.get_hot_facts()` docstring; `thermal_gradient.py` cutoff |

This created a silent split: the stated engineering intent was 0.70, but the
running code filtered at 0.80.

## Decision

Set `TIER_HOT_BOUNDARY = VRAM_ADMISSION_THRESHOLD = 0.7000` and propagate it
to every place that previously hardcoded `0.80`.

## Evidence

The sealed TRS verification package (`research/trs_verification_package/`)
contains a 500-trial parameter sweep (`automated_learning_loop.py`) and a
300-trial fine-grained sweep (`fine_grained_sweep.py`). Both are reproduced
byte-for-byte by running the benchmarks (all 15 package files match
`SHA256SUMS_SEALED`).

Summary from `raw_sweep_results.json` (500 trials/point, α = 0.050):

| θ_HOT | Items | Tokens | Recall | Miller |
|---|---|---|---|---|
| 0.70 | 10.51 | 401 | 86.9% | ✗ (marginal) |
| 0.725 | 6.94 | 263 | 66.7% | ✓ |
| 0.80 | 1.28 | 48 | **5.6%** | ✗ |
| 0.85 | 1.00 | 37 | **0.0%** | ✗ |

The 300-trial fine-grained sweep (simpler synthetic workload with hardcoded
target heats in [0.71, 0.92]) reports 100% recall at θ = 0.70 because all
five target nodes exceed 0.70. The 500-trial sweep's targets span 0.71–0.92
but their mean sits closer to 0.75, explaining the 87% recall.

**Key finding:** 0.80 starves the working set to fewer than 2 items and drops
recall to near zero. 0.70 is a safe lower bound: it admits everything the
prior (broken) 0.80 setting admitted, plus the marginal items that were
silently lost.

## Tradeoffs

- **More admitted items at 0.70 vs 0.725:** The 0.725 point passes Miller's
  Law (7 ± 2 items) more cleanly in the 500-trial run. However, 0.725 drops
  recall to 67% and misses creative-spark nodes. 0.70 is chosen as the
  floor: it always passes the 300-trial sweep, and the τ gate
  (`loci_engine/tau_gate.py`) provides a second-stage filter that handles
  context-flooding independently.
- **Workload sensitivity:** These are synthetic workloads. Real deployment
  should log per-query item counts and tune upward toward 0.725 if working
  sets grow too large.

## Consequences

- `TIER_HOT_BOUNDARY` and `VRAM_ADMISSION_THRESHOLD` are now a single
  constant (both 0.70), eliminating the silent inconsistency.
- Storage, thermal gradient, retrieval, and the τ gate all use the same
  boundary.
- The 300-trial sweep is now a CI test: `tests/integration/test_trs_package.py`.
