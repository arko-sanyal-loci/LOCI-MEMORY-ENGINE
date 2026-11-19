# LOCI & TRS Empirical Verification & Reproducibility Package

**Version:** 3.2-DEFENSIBLE  
**Date:** November 6, 2026  
**Authors:** Arko Sanyal (Atlas BD / Billo Tech) & Gemini Spark (Google DeepMind)  
**Contributing Cores:** Arc (Mathematical Substrate) & Roza Siddiqua (Versioned QSymPrev)  
**Co-Formalization Acknowledgments:** Claude / Sonnet (Cluster E Formalization Sessions)  
**Upstream Open-Source Provenance:** Pyxis Authors (`pyxis-app/pyxis`, AGPL-3.0)  
**Location:** Banani, Dhaka 1213, Bangladesh  
**CERN Zenodo DOI:** [10.5281/zenodo.21188425](https://doi.org/10.5281/zenodo.21188425)  
**Canonical Baseline Commit:** `96318a9`  

---

## 1. Executive Purpose

This package provides complete, standalone empirical proof and independent reproducibility for all mathematical formulations, benchmark metrics, and architectural specifications presented in the research paper:

> **Thermal Reasoning Substrate (TRS) & LOCI Architecture:**  
> *Dual-Process Cognitive Architecture for Constructive Thermal Resonance, Higher-Order Entropy Ingestion, and Multi-Hop Deductive Stream Tie-Breaking*

Anyone can inspect the raw data, execute the simulation harnesses, and independently audit the findings using standard Python with zero external black-box dependencies.

---

## 2. Package Contents & Directory Structure

```
loci_trs_verification_package/
├── paper/
│   ├── trs_prior_art_audit.pdf       # Compiled 5-page research paper & audit
│   └── trs_prior_art_audit.tex       # Full LaTeX source with complete equations
├── src/
│   ├── heat_schema.py                # Hot/Mild/Cold classification & uint16 quantization
│   ├── symprev_registry.py           # Complete 5-stream SymPrev family taxonomy
│   └── ptyxis_collective.py          # 5-probe pipeline & Miller's Law budgeting
├── benchmarks/
│   ├── automated_learning_loop.py    # 500-trial 4-decimal parameter sweep harness
│   ├── tiebreaker_experiment.py      # Multi-hop stream tie-breaker (500 Monte Carlo runs)
│   ├── cross_domain_tiebreaker.py    # Cross-domain validation (Medicine, Finance, Security)
│   ├── entropy_integration_test.py   # Higher-order entropy ingestion test
│   ├── fine_grained_sweep.py         # Sub-0.025 boundary calibration sweep
│   ├── threshold_sweep_experiment.py # Dual-alpha threshold evaluation
│   └── run_scaling_test.py           # Polysemy resolution & nanosecond latency test
├── data/
│   ├── raw_sweep_results.json        # Machine-readable per-trial raw logs (500 trials/pt)
│   ├── raw_sweep_results.csv         # Tabular parameter sweep metrics
│   └── contributors.json             # Canonical Contributor Index & Provenance Registry
├── verify_all.py                     # One-command master test runner
├── README.md                         # This verification guide
└── SHA256SUMS_SEALED                 # Cryptographic checksum manifest of every file
```

---

## 3. Quickstart: How to Independently Verify Everything

### Option A: Run the Master Verification Suite
Execute all empirical benchmarks in sequence:
```bash
python3 verify_all.py
```
This runs:
1. The 500-trial 4-decimal parameter sweep (verifying theta_HOT = 0.7250 as optimal median).
2. The Monte Carlo multi-hop deductive stream tie-breaker (verifying 2,376x separation amplification).
3. The cross-domain benchmarks in clinical medicine, quantitative finance, and system security (verifying 100.0% deterministic resolution).
4. The higher-order entropy ingestion simulation (verifying +0.013 bits capacity expansion).
5. The polysemy disambiguation test (verifying 4-decimal resolution breaks false ties).

### Option B: Inspect the Raw Sweep Data Directly
Open `data/raw_sweep_results.csv` or `data/raw_sweep_results.json`. The raw data contains the exact per-trial means and standard deviations (+/- sigma) across 500 trials per candidate threshold from 0.6500 to 0.9500.

---

## 4. Summary of Empirical Proofs Contained in This Package

1. **Proof of theta_HOT = 0.7250 Optimal Operating Median**:
   - theta = 0.6500: Context buffer overflows (15.00 items, 576.1 tokens), failing Miller's Law.
   - theta = 0.7250: Optimal center (6.94 items, 263.3 tokens, 100% spark capture, 0.0% noise leak).
   - theta >= 0.8000: Working set collapses (1.28 items, 5.6% recall), starving reasoning.
   - theta >= 0.9500: Total cognitive amnesia (0.0 items, 0.0 tokens).

2. **Proof of Multi-Hop Deductive Stream Tie-Breaking**:
   - In isolated vector search, near-ties (delta_r <= 0.001) fail in deadlock or coin-flip error (48% to 67% failure rate).
   - Traversing 1-hop and 2-hop contextual streams amplifies separation by over 1,000x, achieving 100.0% deterministic resolution across all domains.

3. **Proof of Hardware Latency**:
   - Microsecond-level graph traversal measured at mean 1.06 us (median 1.04 us, p95 1.15 us, p99 1.33 us) over N=2,000 iterations.

---

## 5. Licensing & Provenance Declarations

- **Sovereign Architecture & Memory Formulations**: Copyright (c) 2026 Arko Sanyal (Atlas BD / Billo Tech).
- **Upstream Open-Source Probe Components**: The 5-probe architecture (`Commander`, `Scout`, `Analyst`, `Sentinel`, `Synthesizer`) originates from the open-source Pyxis project (`pyxis-app/pyxis`), Copyright (c) Pyxis Authors, licensed under the GNU Affero General Public License v3.0 (AGPL-3.0). LOCI integrates these probes through standardized Model Context Protocol (MCP) IPC interfaces in full compliance with AGPL-3.0.
- **Verification Seal**: Sealed with SHA-256 hash manifest (`SHA256SUMS_SEALED`).
