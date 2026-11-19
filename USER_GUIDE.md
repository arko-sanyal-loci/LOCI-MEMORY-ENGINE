# LOCI Memory Engine — User Guide

## Overview

LOCI is a heat-tiered, persistent memory substrate for long-horizon AI agents.
It stores facts as thermodynamic entities: they heat up under attention and cool
under neglect, migrating between VRAM, host RAM, and NVMe tiers. Three design
pillars drive every component:

| Pillar | Description |
|---|---|
| **Organisation** | Ingest, chunk, embed, store — a document becomes searchable chunks with content-addressed IDs |
| **Guidance** | CARD-routed retrieval, τ-gate trust signal, MRR targets, provenance weighting |
| **Efficiency** | Heat-tiered routing, TF-IDF compression, Miller's Law working-set budget (≤ 9 items) |

---

## Installation

```bash
# Core engine (no model server required for memory operations)
pip install -e .

# With RAG pipeline + MCP coordination server
pip install -e ".[dev,mcp]"

# With sovereign bridge (FastAPI)
pip install -e ".[bridge]"
```

Python ≥ 3.10 required. sqlite-vec needs SQLite ≥ 3.41.

---

## Quick start

### 1 — Ingest documents

```python
from rag.pipeline import ingest, query

# Point at a folder of .txt / .md / .pdf files
n = ingest("./my_docs")
print(f"Ingested {n} chunks")
```

### 2 — Query

```python
result = query("What is the HOT tier boundary?")
print(result["answer"])
print(result["sources"])
print(result["gate"])        # τ-gate decision
print(result["compression"]) # TF-IDF stats if compression is on
```

### 3 — CLI via pytest (verify everything works)

```bash
pytest -q                            # 272 pass, 9 skip
pytest tests/integration/ -v        # offline end-to-end pipeline
cd research/trs_verification_package && python verify_all.py  # 5/5 TRS suites
```

---

## Configuration — environment variables

| Variable | Default | Purpose |
|---|---|---|
| `RAG_DB_PATH` | `./loci_rag.db` | SQLite database for chunks + vectors |
| `RAG_DATA_DIR` | `./data` | Document directory for `ingest()` |
| `RAG_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama model for embeddings |
| `RAG_LLM_MODEL` | `llama3.2` | Ollama model for generation |
| `RAG_OLLAMA_HOST` | `http://localhost:11434` | Ollama server URL |
| `RAG_COMPRESS_RATIO` | `0` (off) | TF-IDF target ratio > 0 enables compression |
| `RAG_ABSTAIN_ON_GATE` | `0` (off) | Set to `1` to abstain when τ gate fails |
| `LOCI_DEVDRIVE` | *(none)* | Dev-drive path for extractor output |
| `LOCI_NODES_ENV` | `config/nodes.env` | Per-machine node config |

---

## Node configuration

Copy `config/nodes.env.example` to `config/nodes.env` (git-ignored) and fill in:

```bash
VPS_HOST=your-server.example.com
VPS_USER=loci
VPS_PATH=/home/loci/LOCI-MEMORY-ENGINE
CONSOLE_USER=your-local-username
```

Then operations scripts in `scripts/ops/` will pick up the values automatically.

---

## Module reference

| Module | Purpose |
|---|---|
| `loci_engine.heat` | Heat law constants, `decay()`, `reinforce()`, `tier()`, `tier_tau()` |
| `loci_engine.storage` | `StorageEngine` — fact store (SQLite WAL), hot/mild/cold recall |
| `loci_engine.vectors` | `VectorStore` — sqlite-vec + FTS5 hybrid RAG store with heat persistence |
| `loci_engine.db` | `open_db()` — WAL + FK-enforced connection factory |
| `loci_engine.provenance` | `resolve_trust()`, `UserStated`, `TRUST_WEIGHTS` |
| `loci_engine.tau_gate` | `dynamic_tau()`, `GateDecision`, `evaluate_mrr()`, MRR targets |
| `loci_engine.compressor` | `TfidfCompressor.compress()` — sentence-level context compression |
| `loci_engine.value_bus` | `ValueBus` — typed-slot scoreboarding between agents |
| `loci_engine.secrets_guard` | `redact()`, `contains_secret()` — 8-family secret scanner |
| `loci_engine.glassbox` | `glassbox_learn()` / `glassbox_recall()` — append-only audit ledger |
| `rag.pipeline` | `ingest()` / `query()` — full RAG pipeline |
| `coordination_bus.bus` | `SecureEventBus`, `TaskBoard` — HMAC inter-agent messaging |

---

## HOT tier boundary

θ_HOT = **0.70**. See `docs/decisions/0001-hot-threshold-0.70.md` for the full
empirical rationale. In brief: 0.80 (the old implicit value) drops recall to
under 6%; 0.70 is the safe lower bound. The τ gate provides a second-stage
context-flood filter.

---

## Running on Intel Arc B70 Pro Sparkle (local GPU)

```bash
# One-time setup (run as root):
sudo LOCI_USER=your-username bash scripts/setup_arc_compute.sh

# Then:
sudo systemctl start loci-ollama-arc
sudo systemctl enable loci-ollama-arc

# Verify:
RAG_OLLAMA_HOST=http://127.0.0.1:11435 python -m pytest -q
```

The service runs Ollama on port 11435 with `GGML_VK_VISIBLE_DEVICES=1`
(Vulkan device index 1 = Arc; device 0 = RTX 5060 Ti).

---

## Security notes

1. **Rotate any key ever processed by the old qSympRev extractor.** Earlier
   builds stored raw API keys to plain text; they are now fingerprinted.
2. `config/nodes.env` is git-ignored. Never commit it.
3. The VPS hostname (`srv1775801.hstgr.cloud`) appears in public git history —
   consider restricting access to that host or rotating any credentials on it.
