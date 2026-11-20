# LOCI research publications

All papers are by Arko Sanyal (Billo Tech). The PDFs, abstracts and reading order live in
[`loci-card-papers`](https://github.com/arko-sanyal-loci/loci-card-papers); full citations and
BibTeX are in its [`REFERENCES.md`](https://github.com/arko-sanyal-loci/loci-card-papers/blob/master/REFERENCES.md).

Papers 01–08 are defensive publications on Technical Disclosure Commons (CC BY 4.0). Publishing
them there places the described techniques in the prior art, so no one can later patent them.
Paper 09 is a preprint, not a TD Commons disclosure.

_Corrected 2026-11-19: the previous version of this file numbered the papers differently from the
PDFs, gave wrong TD Commons article numbers, listed a paper ("Goal-Conditioned Switched Decay —
Implementation") that does not exist, and said all nine were TD Commons publications. Numbers and
article IDs below are taken from each PDF's cover page._

| # | Paper | TD Commons | Date | Where it lives in this repo |
|---|---|---|---|---|
| 01 | Forecasting Affective State from Interaction Streams (LOCI r+e) | [11089](https://www.tdcommons.org/dpubs_series/11089) | 2026-07-21 | Not implemented yet |
| 02 | Reflection-on-Action: Label-Free Learning from Behavioral Outcomes (LOCI e+r) | [11090](https://www.tdcommons.org/dpubs_series/11090) | 2026-07-21 | Not implemented yet (planned `reflect.py`) |
| 03 | A Separate, Fast-Decaying Memory Spectrum for a System's Own Thoughts | [11091](https://www.tdcommons.org/dpubs_series/11091) | 2026-07-21 | Not implemented yet |
| 04 | Category-Adaptive Recall Depth (CARD), validated on LongMemEval-500 | [10856](https://www.tdcommons.org/dpubs_series/10856) | 2026-07-09 | `loci_engine/card_router.py`, `loci_engine/session_ingester.py`, `rag/card.py` |
| 05 | LOCI: A Heat-Decaying, Goal-Conditioned Memory Architecture for Long-Horizon AI Agents | [11666](https://www.tdcommons.org/dpubs_series/11666) | 2026-09-09 | `loci_engine/heat.py`, `loci_engine/storage.py`, `loci_engine/loop_guard.py` (circuit breaker), `loci_engine/dream_engine.py` (Imagination Engine) |
| 06 | Focused Retention: Goal-Conditioned Switched Decay (LOCI) | [11092](https://www.tdcommons.org/dpubs_series/11092) | 2026-07-21 | Partly, in `loci_engine/storage.py` |
| 07 | LOCI ∞: Infinity Memory Middleware with Temporal Compression | [10806](https://www.tdcommons.org/dpubs_series/10806) | 2026-07-06 | `loci_engine/session_continuity.py` (LDCE compression) |
| 08 | LOCI Persistent AI Memory Engine: Versioned Exact-Fact Chains, Source-Trust Provenance | [10843](https://www.tdcommons.org/dpubs_series/10843) | 2026-07-09 | `loci_engine/storage.py` (`upsert_fact`, `get_fact_at`, `get_fact_history`), `loci_engine/store.py` |
| 09 | Thermal Reasoning Substrate: A Heat-Driven Shared Memory Architecture for Parallel LLM Inference | preprint | — | `loci_engine/thermal_gradient.py` (not wired in yet) |

The module mapping comes from searching the code for each paper's named mechanisms. Where a cell
says "partly" or "not yet", the paper describes more than the code does today.
