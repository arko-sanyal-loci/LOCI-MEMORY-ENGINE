# LOCI Research Publications

All LOCI research is published as **defensive publications** via TD Commons, ensuring the work
remains in the public domain and cannot be patented by third parties.

**Author on all papers:** Arko Sanyal (Billo Tech / Atlas BD)
**Zenodo DOI (collection):** [10.5281/zenodo.21188425](https://doi.org/10.5281/zenodo.21188425)

---

## Publications

### Paper 01 — LOCI: Longitudinal Observation and Compression Interface

**Short title:** LOCI main architecture paper
**TD Commons series:** Art. 11666 (co-inventor: Roza Sanyal, Arc)

Introduces the LOCI architecture: heat-tiered persistent memory for long-horizon AI agents.
Defines the open-interval heat invariant, the Constant of Hope (α), and the hardware tier schema
(HOT/MILD/COLD). Specifies the θ-gate (0.82) for mood-law and crisis/venting split, the
forecasting module (r+e), and the full memory hierarchy design.

Implemented in: `loci_engine/heat.py`, `loci_engine/storage.py`, `loci_engine/unified_core.py`

---

### Paper 02 — Reflection-on-Action: Label-Free Learning (LOCI e+r)

**Short title:** e+r reflection
**TD Commons series:** Art. 11090

Defines behavioral-surprise updates: when an agent's prediction diverges from observed outcome,
the heat of the relevant memory is updated without requiring a labeled training signal. Specifies
the anti-hallucination invariant: reflection cannot increase confidence in an unobserved fact.

Planned implementation: `loci_engine/reflect.py` (Plan 4)

---

### Paper 03 — Separate Fast-Decaying Memory Spectrum for System Thoughts

**Short title:** Thoughts spectrum
**TD Commons series:** Art. 11090 (sub-paper)

Specifies a separate memory spectrum for internal agent reasoning ("thoughts"), decaying faster
than observation memory. Prevents system-level reasoning traces from polluting the long-term
fact store while still being addressable during a session.

Planned implementation: `loci_engine/thoughts.py` (Plan 3)

---

### Paper 04 — Category-Adaptive Recall Depth (CARD) for Heat-Tiered Memory Systems

**Short title:** CARD
**TD Commons:** Art. 10856 / Series referencing #10856

Formalizes the query-classification → recall-depth mapping. Defines four archetypes
(information_extraction, knowledge_update, multi_session_reasoning, temporal_reasoning) and
their associated K values and ranking strategies. Allows three classification methods:
keyword-heuristic (implemented), learned classifier, and LLM-based.

Implemented in: `loci_engine/card_router.py`, `loci_engine/session_ingester.py`, `rag/card.py`

---

### Paper 05 — Focused Retention: Goal-Conditioned Switched Decay

**Short title:** GCSD Part I
**TD Commons series:** Art. 11092

Defines the Goal-Conditioned Switched Decay (GCSD) mechanism: memory items locked to an active
goal decay at a reduced rate (or not at all), switching back to standard decay once the goal
is resolved. Specifies per-tier half-life models:
critical / high / decision / normal goal classes with distinct τ values.

Planned implementation: `loci_engine/goal_retainer.py` (Plan 3)

---

### Paper 06 — Goal-Conditioned Switched Decay — Implementation

**Short title:** GCSD Part II
**TD Commons series:** Art. 11092 (sub-paper)

Implementation specification for GCSD: the goal-lock table schema (`goal_state`, `goal_lock`
already in `storage.py`), the foreground/background invariant, lock strength tiers (anchor vs.
dependency), and the release-event protocol. The schema is live; the decay-switch logic is
pending Plan 3.

Schema implemented in: `loci_engine/storage.py` (goal_state, goal_lock tables)

---

### Paper 07 — LOCI ∞ — Infinity Memory Middleware

**Short title:** LOCI Infinity / multi-node
**TD Commons:** Art. 12121

Specifies LOCI's multi-node operation: the NodeSyncDaemon protocol, WAL-based change detection,
CRDT merge rules (Last-Write-Wins heat, lattice-based status), Merkle tree divergence detection,
and the Glassbox cross-node synchronization protocol. Defines the wire format for SyncDelta.

Implemented in: `loci_engine/node_sync_daemon.py`, `loci_engine/glassbox.py`

---

### Paper 08 — Versioned Fact Storage with Source Trust

**Short title:** Fact versioning + provenance
**TD Commons:** MS #12159

Defines the append-only fact versioning schema (`supersedes`/`valid_from`/`valid_until`),
source trust levels (UserStated → 1.0, system_derived → 0.5), the asymmetric conflict gate
(GATE_LOWER=0.8, GATE_HIGHER=1.2), and the provenance boundary enforcement
(fail-closed default for anything not an actual `UserStated` instance).

Implemented in: `loci_engine/storage.py` (memory_item schema), `loci_engine/glassbox.py`

---

### Paper 09 — LOCI Heat-Tiered Memory Architecture (Main Technical Paper)

**Short title:** LOCI technical spec
**TD Commons:** Art. 13008 / Series 11666

The full technical specification: SQLite WAL schema (`isymprev`/`qsymprev` → canonical
`memory_item`), heat activation mathematics (A1–A3 with proofs), hardware tier routing,
the SLP arena (SymLinkPrev, Host RAM tier), sqlite-vec + FTS5 hybrid search with Reciprocal
Rank Fusion, and the entity graph design (1/2/3-hop spreading activation — deferred to Plan 3).
Appendix B specifies the canonical tier boundaries and tau values, validated empirically by
Spark (Nov 2026).

Implemented in: `loci_engine/heat.py`, `loci_engine/storage.py`, `loci_engine/slp_arena.py`,
`loci_engine/store.py`

---

## Zenodo Collection

All 9 papers are archived at:

**DOI:** [10.5281/zenodo.21188425](https://doi.org/10.5281/zenodo.21188425)

This DOI provides a citable, permanent record. The TD Commons filings establish prior art and
ensure all LOCI mechanisms remain unpatentable by any party.

---

## Related Repositories (by Arko Sanyal)

- **loci-card-papers** (`arko-sanyal/loci-card-papers`) — paper PDFs with one-paragraph summaries
- **loci-coordination-bus** (`arko-sanyal/loci-coordination-bus`) — multi-agent event log + task
  board (separate from this memory engine)

---

*Citations, corrections, or additions: open an issue in the canonical repository
(`arko-sanyal-loci/loci-memory-engine`).*
