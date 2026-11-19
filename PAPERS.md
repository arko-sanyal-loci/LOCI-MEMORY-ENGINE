# LOCI research papers

Nine papers by Arko Sanyal describe the mechanisms this engine implements. The PDFs live in
[`loci-card-papers`](https://github.com/arko-sanyal-loci/loci-card-papers).

Every title, date and article number below was read from the PDF itself on 2026-11-19
(`pdftotext`, cover page). An earlier version of this file listed titles and article numbers
that did not match the PDFs; this version replaces it.

Papers 01–08 are Technical Disclosure Commons (TD Commons) defensive publications, licensed
CC BY 4.0. Paper 09 is an independent preprint (cs.AI, cs.CL), not a TD Commons disclosure.

Zenodo collection DOI: [10.5281/zenodo.21188425](https://doi.org/10.5281/zenodo.21188425)

## Publications

| # | Title (as on the PDF) | Published | TD Commons | Implemented in |
|---|---|---|---|---|
| 01 | Forecasting Affective State from Interaction Streams: A Closed Loop with Heat-Decay Memory, Label-Free Mood Estimation, and Trajectory-Based Crisis/Venting Separation (LOCI r+e) | 21 Jul 2026 | [11089](https://www.tdcommons.org/dpubs_series/11089) | Not yet (θ = 0.82 confidence gate is specified, not built) |
| 02 | Reflection-on-Action: Label-Free Learning from Behavioral Outcomes in Interactive Agents (LOCI e+r) | 21 Jul 2026 | [11090](https://www.tdcommons.org/dpubs_series/11090) | Planned (`reflect.py`) |
| 03 | A Separate, Fast-Decaying Memory Spectrum for a System's Own Thoughts, with Reflection-Gated Crystallization (LOCI) | 21 Jul 2026 | [11091](https://www.tdcommons.org/dpubs_series/11091) | Planned (`thoughts.py`) |
| 04 | Category-Adaptive Recall Depth (CARD) for Heat-Tiered Memory Systems, with Experimental Validation on LongMemEval-500 | 09 Jul 2026 | [10856](https://www.tdcommons.org/dpubs_series/10856) | `loci_engine/card_router.py`, `loci_engine/session_ingester.py`, `rag/card.py` |
| 05 | LOCI: A Heat-Decaying, Goal-Conditioned Memory Architecture for Long-Horizon AI Agents | 09 Sep 2026 | [11666](https://www.tdcommons.org/dpubs_series/11666) | `loci_engine/heat.py`, `loci_engine/storage.py`, `loci_engine/loop_guard.py` |
| 06 | Focused Retention: Goal-Conditioned Switched Decay as an Active Anti-Decay Force in Agent Memory (LOCI) | 21 Jul 2026 | [11092](https://www.tdcommons.org/dpubs_series/11092) | Schema only (`goal_state`, `goal_lock` in `storage.py`) |
| 07 | LOCI ∞: Infinity Memory Middleware with Temporal Compression and Universal Cross-Platform Injection | 06 Jul 2026 | [10806](https://www.tdcommons.org/dpubs_series/10806) | Partly: the two streams are unified into one `memory_item` table in `storage.py` |
| 08 | LOCI Persistent AI Memory Engine: Versioned Exact-Fact Chains, Source-Trust Provenance Weighting, Hardware-Tier Gradient Search, and Interpersonal Quality-of-Life Gating | 09 Jul 2026 | [10843](https://www.tdcommons.org/dpubs_series/10843) | `loci_engine/storage.py` (`supersedes` / `valid_from` / `valid_until`), `loci_engine/glassbox.py` |
| 09 | Thermal Reasoning Substrate: A Heat-Driven Shared Memory Architecture for Parallel LLM Inference | Preprint | — | `loci_engine/heat.py`, `loci_engine/slp_arena.py` |

Reading order: numeric. 07 → 08 → 09 are one continuous architecture; 01 and 02 are companion
papers on the same closed loop. One-paragraph summaries of each paper are in the
[`loci-card-papers` README](https://github.com/arko-sanyal-loci/loci-card-papers#papers).

## How to cite

```
Sanyal, Arko. "<title>". Technical Disclosure Commons, (<date>).
https://www.tdcommons.org/dpubs_series/<number>
```

## Related repositories

- [`loci-card-papers`](https://github.com/arko-sanyal-loci/loci-card-papers): the PDFs.
- [`arc`](https://github.com/arko-sanyal-loci/arc): the local runtime that uses this engine.

Corrections: open an issue on
[`LOCI-MEMORY-ENGINE`](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/issues).
