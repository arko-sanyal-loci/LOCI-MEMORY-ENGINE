# Archive

This directory holds historical artefacts that are no longer part of the
active codebase but are kept for audit and reference.

## patches/

Three ops patches from the `mac-install` rescue effort:

| File | Status | Notes |
|---|---|---|
| `0001-gpu-param-size-naming.patch` | Partially applied | GPU `param_size` → `vram_budget_gb` rename; some hunks already applied to `loci_engine/` |
| `0002-unify-ethics-layer.patch` | Partially applied | Extracts Learning Core from ethics.py; not fully integrated |
| `0003-e2e-ethics-benchmark.patch` | Fully applied | End-to-end ethics benchmark — already in `benchmarks/e2e_ethics_layer.py` |

## one-shot/

Scripts that were written for a one-time station-0 handoff procedure:

- `finalize_station0.sh` — final cleanup script for the initial workstation setup
- `push_station0.sh` — initial push script

These are not part of the regular operations workflow; use `scripts/ops/` instead.
