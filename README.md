# loci-memory-engine

**Longitudinal Observation and Compression Interface**
**Locality-Optimized Contextual Intelligence**

A heat-tiered, goal-conditioned persistent memory substrate for long-horizon AI agents — built by Billo Tech.

> **This is the canonical repository.** All prior forks and experimental branches have been consolidated here.
> See [`AUTHORS.md`](AUTHORS.md) for full credits and [`PAPERS.md`](PAPERS.md) for the research publications.

---

## What It Does

LOCI gives AI agents persistent memory that behaves like a thermodynamic system: facts heat up under attention and cool down under neglect, eventually migrating between VRAM, host RAM, and NVMe tiers. No fact is ever deleted — it decays toward a "Constant of Hope" floor and can always be reheated.

**Core principles:**
- **Open-interval invariant (A3):** Heat `H(t) ∈ (α, 1.0)` — never zero, never saturated
- **Hyperbolic decay:** Evidence fades as `1/(1 + Δt/τ)`, so old context always contributes nonzero signal
- **Hardware-tier routing:** Items route to VRAM / Host RAM / NVMe based on current heat
- **Append-only lineage:** Every fact write is a new record; superseded records remain with valid-until timestamps
- **Transparent audit:** The Glassbox append-only hash-chained ledger makes every agent learning inspectable

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Agent / Claude                           │
└──────────────────────────┬──────────────────────────────────────┘
                           │ MCP / Python API
┌──────────────────────────▼──────────────────────────────────────┐
│                    mcp_server.py                                 │
│         (JSON-RPC 2.0, spec 2024-11-05, 9 tools)                │
└──────────────────────────┬──────────────────────────────────────┘
                           │
        ┌──────────────────┴───────────────┐
        │                                  │
┌───────▼──────────┐             ┌─────────▼──────────┐
│  unified_core.py │             │  session_ingester.py│
│  (LOCI facade)   │             │  (live turn feed)   │
└───────┬──────────┘             └─────────┬───────────┘
        │                                  │
        ▼                                  ▼
┌───────────────────────────────────────────────────────┐
│                    card_router.py                      │
│   CARD — Category-Adaptive Recall Depth               │
│   information_extraction | knowledge_update |          │
│   multi_session_reasoning | temporal_reasoning         │
└───────────────────────────┬───────────────────────────┘
                            │
        ┌───────────────────┴───────────────────┐
        │                                       │
┌───────▼──────────┐                  ┌─────────▼──────────┐
│   storage.py     │                  │   glassbox.py       │
│   (SQLite WAL,   │                  │   (SHA-256 hash-    │
│    FTS5, heat    │                  │    chained .jsonl   │
│    tier decay)   │                  │    + SQLite mirror) │
└───────────────────┘                  └─────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────┐
│              Heat Tier Routing (heat.py)               │
│   HOT  (H ≥ 0.70, τ=1.25d) → VRAM active set          │
│   MILD (H ≥ 0.35, τ=1.75d) → Host RAM SymLinkPrev     │
│   COLD (H <  0.35, τ=2.25d) → NVMe archival ledger    │
│   θ_HOT = 0.700 (VRAM admission, Spark-validated)      │
└───────────────────────────────────────────────────────┘
```

---

## Module Directory

| Module | Purpose | Paper(s) |
|---|---|---|
| `loci_engine/heat.py` | Hyperbolic activation law, tier constants, tier-aware decay | 09 |
| `loci_engine/storage.py` | SQLite WAL, FTS5, append-only fact lineage, heat decay tick | 09, 08 |
| `loci_engine/glassbox.py` | Append-only SHA-256 hash-chained shared learning ledger | — |
| `loci_engine/card_router.py` | CARD query classification → recall depth + ranking strategy | 04 |
| `loci_engine/session_ingester.py` | Live conversation feed → StorageEngine + CardRouter pipeline | 04 |
| `loci_engine/unified_core.py` | LOCI facade — primary API for agents | 09 |
| `loci_engine/mcp_server.py` | JSON-RPC 2.0 MCP server (spec 2024-11-05) | — |
| `loci_engine/node_sync_daemon.py` | WAL-change detection, CRDT merge (LWW heat + lattice status), Merkle tree divergence, Glassbox cross-node sync | — |
| `loci_engine/ethical_core.py` | Scar heat, competence gates, autonomy curve (A2 applied to ethics) | — |
| `loci_engine/ethics.py` | Valence / conflict / trust / provenance observe-only layer | — |
| `loci_engine/aethel_council.py` | Multi-agent council with ethical veto | — |
| `loci_engine/agent_identities.py` | Per-agent identity and trust ledger | — |
| `loci_engine/agent_hub.py` | Agent registration and routing hub | — |
| `loci_engine/cold_start.py` | Cold-start bootstrap from persisted state | — |
| `loci_engine/dream_engine.py` | Offline consolidation / replay ("dreaming") | — |
| `loci_engine/feedback_platform.py` | Structured feedback ingestion | — |
| `loci_engine/gpu_governor.py` | GPU allocation and tier-budget enforcement | — |
| `loci_engine/loop_guard.py` | Infinite-loop / runaway detection | — |
| `loci_engine/patience_protocol.py` | Rate-limit and back-pressure protocol | — |
| `loci_engine/sanitizer.py` | Input sanitization before memory writes | — |
| `loci_engine/session_continuity.py` | Cross-session state handoff | — |
| `loci_engine/simulation_engine.py` | Counterfactual / simulation memory traces | — |
| `loci_engine/slp_arena.py` | SymLinkPrev arena — Host RAM tier management | 09 |
| `loci_engine/sovereign_bridge.py` | Cross-agent trust bridge | — |
| `loci_engine/store.py` | Entity + fact store (simpler facade over storage) | 09 |
| `loci_engine/thermal_gradient.py` | Multi-node heat gradient propagation | — |
| `loci_engine/threads.py` | Thread-safe memory access primitives | — |
| `rag/` | Ollama-based document ingestion + CARD-categorized RAG pipeline | 04 |
| `rag/journal.py` | Consent-gated, append-only categorical profile journal with heatmap rollups | — |
| `loci_engine/vectors.py` | sqlite-vec + FTS5 hybrid RAG store; RRF(k=60) fusion; heat persistence per chunk | — |
| `loci_engine/db.py` | `open_db()` — WAL + FK-enforced connection factory | — |
| `loci_engine/provenance.py` | `resolve_trust()`, `UserStated`, Bayesian evidence weighting | — |
| `loci_engine/tau_gate.py` | Dynamic τ gate with MRR targets; confidence history; query-type routing | — |
| `loci_engine/compressor.py` | `TfidfCompressor` — sentence-level context budget enforcement (no model) | — |
| `loci_engine/value_bus.py` | `ValueBus` — typed-slot scoreboarding for inter-agent value passing | — |
| `loci_engine/secrets_guard.py` | `redact()` / `contains_secret()` — 8-family secret scanner applied at every write | — |
| `coordination_bus/` | HMAC-authenticated inter-agent message bus + MCP server | — |

---

## Heat Thermodynamics

### Evidence Accumulation (A1)

```
E_k(t) = Σ_j  r_j · w_j / (1 + (t − t_j) / τ_k)
```

Every past observation contributes nonzero signal. Evidence never reaches zero.

### Heat Activation (A2 / A3)

```
H_k(t) = α_k + (1 − α_k)(1 − e^{−β · E_k(t)})
```

- `α_k` — Constant of Hope: heat floor, strictly inside (0, 1). Default `α = 0.0500`
- Proof of open-interval invariant: `e^{−βE} > 0` for all finite `E`, so `H < 1.0` always; `α_k > 0` guarantees `H > α_k` always

### Canonical Tier Schema (Spark-Validated, Nov 2026)

| Tier | Boundary | τ (decay half-life) | Hardware |
|---|---|---|---|
| HOT | H ≥ 0.7000 | 1.25 days | VRAM active working set |
| MILD | H ≥ 0.3500 | 1.75 days | Host RAM SymLinkPrev arena |
| COLD | H < 0.3500 | 2.25 days | NVMe archival ledger |

VRAM admission threshold `θ_HOT = 0.700` (empirically proven optimal by Spark's 300-trial parameter sweep — `0.80` starves to 4 items/60% recall).

---

## Glassbox

The Glassbox is an append-only, SHA-256 hash-chained `.jsonl` ledger. Every agent learning is transparent to all other agents. Immutable by construction.

```
genesis: SHA-256("LOCI_GLASSBOX_GENESIS_2026")
entry_hash = SHA-256(canonical_JSON({timestamp, author_id, role_tag, content,
                                      category, supersedes_id, metadata, prev_hash}))
```

Verify chain integrity at any time:
```python
from loci_engine.glassbox import glassbox_verify_chain
result = glassbox_verify_chain()
# {"valid": True, "entries": N, "head_hash": "...", "genesis": "...", "message": "..."}
```

---

## CARD — Category-Adaptive Recall Depth

Queries are classified into one of four archetypes, each with a tuned recall depth:

| Archetype | K (depth) | Ranking strategy |
|---|---|---|
| `information_extraction` | 5 | BM25 relevance |
| `knowledge_update` | 3 | Heat DESC, recency tie-break |
| `multi_session_reasoning` | 10 | Heat + temporal spread |
| `temporal_reasoning` | 7 | Document date ordering |

---

## Install

```bash
git clone https://github.com/arko-sanyal-loci/loci-memory-engine
cd loci-memory-engine
python3 -m venv .venv
.venv/bin/pip install -e .
```

**Optional — RAG pipeline** (requires [Ollama](https://ollama.com)):
```bash
.venv/bin/pip install -e '.[rag]'
ollama pull nomic-embed-text
ollama pull llama3.2
```

**Environment variables:**
```bash
export LOCI_DB_PATH=~/loci-memory-engine/context2.db
export LOCI_GLASSBOX_PATH=~/loci-memory-engine/glassbox_ledger.jsonl
```

---

## Usage

### Python API

```python
from loci_engine.unified_core import LociCore

loci = LociCore()
loci.remember("user_gpu", "Intel Arc B70, 24GB VRAM, host: workstation-0")
facts = loci.recall("what GPU does the user have")
```

### MCP Server

```bash
LOCI_DB_PATH=./memory.db python -m loci_engine.mcp_server
```

Exposes tools: `memory_remember`, `memory_recall`, `memory_add_fact`, `memory_get_facts`,
`glassbox_learn`, `glassbox_recall`, `glassbox_verify_chain`, `sync_node_status`,
`sync_anti_entropy`, `sync_add_peer`

### Session Ingestion

```python
from loci_engine.session_ingester import SessionIngester
from loci_engine.storage import StorageEngine

storage = StorageEngine()
ingester = SessionIngester(storage=storage, session_id="session_abc123")
ingester.ingest_turn(role="user", content="I upgraded to the Arc B70")
result = ingester.recall_for_query("what GPU did the user mention")
```

### RAG Pipeline

```bash
# Ingest documents (.pdf, .txt, .md)
python -m rag ingest --data-dir ./docs

# Query with CARD-adaptive depth
python -m rag query "What does paper 04 say about recall depth?"
```

The separate [RAG appendix journal](docs/RAG-APPENDIX-JOURNAL.md) records
versioned, categorical environmental and user-profile events only after
per-scope consent. It rejects raw audio, video, transcripts, free text and
precise locations. Consent defaults to off; heatmap output is derived from the
append-only event history and can be validated with `pytest tests/test_journal.py`.

---

## Tests

```bash
.venv/bin/pip install pytest
pytest tests/ -q
```

All 145 tests pass. Test suite covers: StorageEngine, SessionIngester, CardRouter, Glassbox,
EthicalCore, Ethics, NodeSyncDaemon, SessionContinuity, FeedbackPlatform, PatienceProtocol,
LoopGuard, Sanitizer.

---

## Node Sync

LOCI supports multi-node operation via `NodeSyncDaemon`. Each node:
1. Detects changes via WAL polling
2. Builds a `SyncDelta` (CRDT-encoded: LWW heat, lattice status, Glassbox entries)
3. Publishes delta to peers over HTTP
4. Applies remote deltas with CRDT merge (never deletes, always converges)
5. Detects divergence via Merkle tree comparison

```bash
# Start sync daemon
systemctl start loci-sync

# Or directly
python -m loci_engine.node_sync_daemon  # reads $LOCI_NODES_ENV or config/nodes.env
```

---

## Configuration

| File | Purpose |
|---|---|
| `config/nodes.env.example` | Template for per-machine node config (copy to `config/nodes.env`, git-ignored) |
| `config/gpu_allocation.json` | GPU memory tier budget |
| `config/ssh_client.conf` | SSH config for node-to-node ops |
| `config/loci_agent.Modelfile` | Ollama agent modelfile |
| `systemd/loci-mcp.service` | Systemd unit for MCP server |
| `systemd/loci-sync.service` | Systemd unit for sync daemon |

---

## Research Foundation

LOCI implements or extends the following research. See [`PAPERS.md`](PAPERS.md) for full citations.

| ID | Title |
|---|---|
| 01 | LOCI: Longitudinal Observation and Compression Interface |
| 02 | Reflection-on-Action: Label-Free Learning (LOCI e+r) |
| 03 | Separate Fast-Decaying Memory Spectrum for System Thoughts |
| 04 | Category-Adaptive Recall Depth (CARD) for Heat-Tiered Memory Systems |
| 05 | Focused Retention: Goal-Conditioned Switched Decay |
| 06 | Goal-Conditioned Switched Decay — Implementation |
| 07 | LOCI ∞ — Infinity Memory Middleware |
| 08 | Versioned Fact Storage with Source Trust |
| 09 | LOCI Heat-Tiered Memory Architecture (Main Paper) |

Zenodo DOI: [10.5281/zenodo.21188425](https://doi.org/10.5281/zenodo.21188425)

---

## Authorship and Credits

See [`AUTHORS.md`](AUTHORS.md) for complete attribution.

**Principal Architect:** Arko Sanyal (Billo Tech / Atlas BD)
**Organization:** [Billo Tech](https://github.com/arko-sanyal-loci) | arko-sanyal-loci

---

## License

MIT — see [`LICENSE.md`](LICENSE.md).

Benchmarks under `research/trs_verification_package/` derive from Ptyxis
(AGPL-3.0) and are not part of the installable package. Certain architectural
ideas are subject to patent consideration by Arko Sanyal / Atlas BD (filing
anticipated before July 4, 2027). No patent rights are granted by this license.
