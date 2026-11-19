<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="brand/billo-tech-logo-dark.svg">
  <img alt="Billo Tech" src="brand/billo-tech-logo-light.svg" width="480">
</picture>

</div>

# LOCI Memory Engine

**Longitudinal Observation and Compression Interface**
**Locality-Optimized Contextual Intelligence**

A heat-tiered, goal-conditioned persistent memory substrate for long-horizon AI agents — built by Billo Tech.

> **This is the canonical repository for the LOCI engine.** Earlier copies (`loci-memory-engine-1`,
> `loci-coordination-bus`, `LOCI-Coordinate-BUS`) are read-only redirects to here.
> See [`AUTHORS.md`](AUTHORS.md) for credits and [`PAPERS.md`](PAPERS.md) for the research.

## Where this fits in LOCI

| Repository | Role |
|---|---|
| **LOCI-MEMORY-ENGINE** (this repo) | The engine: heat-tiered memory, CARD recall, the Glassbox ledger, ethics gate, coordination bus |
| [arc](https://github.com/arko-sanyal-loci/arc) | Local runtime and LOCI co-author: runs models on your GPUs with this engine as memory |
| [loci-card-papers](https://github.com/arko-sanyal-loci/loci-card-papers) | The published LOCI / CARD papers the code implements |

Individual modules connect and unify under **The Glassbox**, the shared, transparent knowledge
compendium that every agent and model can read from and contribute to.

New here? Start with the [user guide](docs/USER_GUIDE.md).

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
│   HOT  (H ≥ 0.80, τ=1.25d) → VRAM active set          │
│   MILD (H ≥ 0.35, τ=1.75d) → Host RAM SymLinkPrev     │
│   COLD (H <  0.35, τ=2.25d) → NVMe archival ledger    │
│   θ_HOT = 0.700 (VRAM admission, Spark-validated)      │
└───────────────────────────────────────────────────────┘
```

---

## Module Directory

| Module | Purpose | Paper(s) |
|---|---|---|
| `loci_engine/heat.py` | Hyperbolic activation law, tier constants, tier-aware decay | 05 |
| `loci_engine/storage.py` | SQLite WAL, FTS5, append-only fact lineage, heat decay tick | 05, 08 |
| `loci_engine/glassbox.py` | Append-only SHA-256 hash-chained shared learning ledger | — |
| `loci_engine/card_router.py` | CARD query classification → recall depth + ranking strategy | 04 |
| `loci_engine/session_ingester.py` | Live conversation feed → StorageEngine + CardRouter pipeline | 04 |
| `loci_engine/unified_core.py` | Identity resolver, valence gate, goodwill ledger, snippet budget engine | — |
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
| `loci_engine/slp_arena.py` | SymLinkPrev arena — Host RAM tier management | 05 |
| `loci_engine/sovereign_bridge.py` | Cross-agent trust bridge | — |
| `loci_engine/store.py` | Entity + fact store (simpler facade over storage) | 05 |
| `loci_engine/thermal_gradient.py` | Gaussian heat-gradient diffusion (not yet wired in; uses its own 0.70 / 0.25 tier cut-offs, see [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md#heat-thresholds)) | 09 |
| `loci_engine/threads.py` | Thread-safe memory access primitives | — |
| `rag/` | Ollama document ingestion, sqlite-vec + FTS5 chunk store (`vector_store.py`), CARD-categorized RAG | 04 |

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
| HOT | H ≥ 0.8000 | 1.25 days | VRAM active working set |
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

Python 3.11 or newer. The core engine and the coordination bus use only the standard library.

```bash
git clone https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE
cd LOCI-MEMORY-ENGINE
python3 -m venv .venv
.venv/bin/pip install -e .            # core engine
.venv/bin/pip install -e '.[mcp]'     # + coordination-bus MCP server
.venv/bin/pip install -e '.[bridge]'  # + HTTP bridge (FastAPI)
```

**Optional: RAG pipeline** (needs [Ollama](https://ollama.com)):
```bash
.venv/bin/pip install -e '.[rag]'
ollama pull nomic-embed-text
ollama pull llama3.2
```

**Environment variables:**
```bash
export LOCI_DB_PATH=~/LOCI-MEMORY-ENGINE/context2.db
export LOCI_GLASSBOX_PATH=~/LOCI-MEMORY-ENGINE/glassbox_ledger.jsonl
```

---

## Usage

### Python API

```python
from loci_engine.storage import StorageEngine

store = StorageEngine()                      # uses $LOCI_DB_PATH
store.upsert_fact("user", "gpu", "Intel Arc B70 Pro, 32 GB")
store.get_current_fact("user", "gpu")["canonical_text"]   # 'user.gpu = Intel Arc B70 Pro, 32 GB'
```

### MCP Server

```bash
LOCI_DB_PATH=./memory.db python -m loci_engine.mcp_server
```

Exposes 33 tools in groups: memory (`memory_search_lexical`, `memory_ingest_fact`), Glassbox
(`glassbox_learn`, `glassbox_recall`, `glassbox_verify`, `glassbox_stats`), agents
(`agent_register`, `agent_send`, ...), sessions (`session_start`, `session_recall`, ...),
feedback, patience, GPU (`gpu_status`, `gpu_route`, ...) and sync (`sync_node_status`,
`sync_anti_entropy`, `sync_force`, `sync_add_peer`). The full list is in the
[user guide](docs/USER_GUIDE.md#mcp-tools).

### Session Ingestion

```python
from loci_engine.session_ingester import SessionIngester
from loci_engine.storage import StorageEngine

storage = StorageEngine()
ingester = SessionIngester(storage=storage, session_id="session_abc123")
ingester.ingest_turn(role="user", content="I upgraded to the Arc B70 Pro, 32 GB")
result = ingester.recall_for_query("what GPU did the user mention")
result["archetype"], result["selected_items"][0]["canonical_text"]
```

### RAG Pipeline

```bash
# Ingest documents (.pdf, .txt, .md)
python -m rag ingest --data-dir ./docs

# Query with CARD-adaptive depth
python -m rag query "What does paper 04 say about recall depth?"
```

---

## Tests

```bash
.venv/bin/pip install -e '.[dev,mcp,rag,bridge]'
.venv/bin/python -m pytest -q
```

228 tests (8 more skip unless Ollama is running), covering storage, CARD routing, the Glassbox chain, ethics, session continuity,
node sync, the coordination bus and its MCP server, the RAG pipeline, GPU routing, the deploy manifest, and an import check of every module. CI runs the same
command on every pull request.

If you change anything in `loci_engine/`, run `scripts/ops/update_manifest.sh` and commit the new
`manifest.sha256`. Deployed nodes compare against it (see Node Sync), and `tests/test_manifest.py`
fails until it is current.

---

## Repository layout

| Path | What lives there |
|---|---|
| `loci_engine/` | The engine package |
| `coordination_bus/` | Secure inter-agent message bus and its MCP server |
| `rag/` | Optional Ollama document pipeline |
| `tests/` | All tests (`pytest`) |
| `scripts/` | Developer scripts; `scripts/ops/` holds machine and VPS operations |
| `systemd/` | Units for the MCP server and the sync daemon |
| `config/`, `architecture/`, `interface/`, `benchmarks/` | Configuration, design notes, UI, benchmarks |
| `agents/` | 32-agent workspace skeleton (see `agents/PHASES.md`) |
| `ledger/` | Hash-chained contributor credit ledger |
| `mac-install/` | Rescued Mac install layer, not yet integrated |
| `brand/` | Billo Tech logo files |
| `docs/` | User guide, repository structure, profile README |
| `archive/` | Applied one-off patches and scripts, kept for history only |

---

## Node Sync

LOCI supports multi-node operation via `NodeSyncDaemon`. Each node:
1. Detects changes via WAL polling
2. Builds a `SyncDelta` (CRDT-encoded: LWW heat, lattice status, Glassbox entries)
3. Publishes delta to peers over HTTP
4. Applies remote deltas with CRDT merge (never deletes, always converges)
5. Detects divergence via Merkle tree comparison

```bash
# scripts/ops/node_sync.sh force-resets the checkout to origin/main when it drifts.
# Run it only on deployment nodes, never on a machine where you edit code.

# Start sync daemon
systemctl start loci-sync

# Or directly
python -m loci_engine.node_sync_daemon --config config/nodes.env
```

---

## Configuration

| File | Purpose |
|---|---|
| `config/nodes.env` | Node addresses and sync intervals |
| `config/gpu_allocation.json` | GPU memory tier budget |
| `config/ssh_client.conf` | SSH config for node-to-node ops |
| `config/loci_agent.Modelfile` | Ollama agent modelfile |
| `systemd/loci-mcp.service` | Systemd unit for MCP server |
| `systemd/loci-sync.service` | Systemd unit for sync daemon |

---

## Research Foundation

LOCI implements or extends the following research. See [`PAPERS.md`](PAPERS.md) for full citations.

| # | Paper |
|---|---|
| 01 | Forecasting Affective State from Interaction Streams (LOCI r+e) |
| 02 | Reflection-on-Action: Label-Free Learning (LOCI e+r) |
| 03 | A Separate, Fast-Decaying Memory Spectrum for a System's Own Thoughts |
| 04 | Category-Adaptive Recall Depth (CARD) |
| 05 | LOCI: A Heat-Decaying, Goal-Conditioned Memory Architecture |
| 06 | Focused Retention: Goal-Conditioned Switched Decay |
| 07 | LOCI ∞: Infinity Memory Middleware |
| 08 | LOCI Persistent AI Memory Engine: Versioned Fact Chains |
| 09 | Thermal Reasoning Substrate (preprint) |

Zenodo DOI: [10.5281/zenodo.21188425](https://doi.org/10.5281/zenodo.21188425)

---

## Authorship and Credits

See [`AUTHORS.md`](AUTHORS.md) for complete attribution.

**Principal Architect:** Arko Sanyal (Billo Tech / Atlas BD)
**Organization:** [Billo Tech](https://github.com/billo-tech) · [arko-sanyal-loci](https://github.com/arko-sanyal-loci)

---

## License

© 2026 Arko Sanyal / Billo Tech. All rights reserved. The source is public to read and cite, not
licensed for reuse. See [`LICENSE.md`](LICENSE.md).
