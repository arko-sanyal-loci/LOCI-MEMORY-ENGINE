# LOCI Memory Engine: User Guide

This guide takes you from a fresh clone to a working memory: storing facts, recalling them with
CARD, writing to the Glassbox, and serving it all to an agent over MCP. Every code block here is
run by `tests/test_e2e_smoke.py`, so if an example stops working, CI fails.

- [1. Install](#1-install)
- [2. Where data lives](#2-where-data-lives)
- [3. Store and search facts](#3-store-and-search-facts)
- [4. Feed a conversation and recall with CARD](#4-feed-a-conversation-and-recall-with-card)
- [5. Heat and tiers](#5-heat-and-tiers)
- [6. The Glassbox](#6-the-glassbox)
- [7. MCP server](#mcp-server)
- [8. RAG over your documents](#8-rag-over-your-documents)
- [9. Running on several machines](#9-running-on-several-machines)
- [10. Using LOCI from Arc](#10-using-loci-from-arc)
- [11. Troubleshooting](#11-troubleshooting)

## 1. Install

Python 3.11 or newer.

```bash
git clone https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE
cd LOCI-MEMORY-ENGINE
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest            # should end with "passed"
```

The core engine and its MCP server use only the standard library. Extras add optional parts:

| Extra | Adds | Needed for |
|---|---|---|
| `dev` | pytest | running the tests |
| `mcp` | `mcp>=1.2,<2` | the coordination bus MCP binding (`coordination_bus/mcp_server.py`) |
| `bridge` | FastAPI, httpx, pydantic | the HTTP bridge (`loci_engine/sovereign_bridge.py`) |
| `rag` | Ollama client, sqlite-vec, pypdf, LangChain splitters | the document pipeline in `rag/` |

Install several at once: `pip install -e '.[dev,mcp,rag]'`.

## 2. Where data lives

| Variable | Default | What it holds |
|---|---|---|
| `LOCI_DB_PATH` | `~/loci-memory-engine/context2.db` | SQLite (WAL) memory store, with FTS5 search |
| `LOCI_GLASSBOX_PATH` | `~/loci-memory-engine/glassbox_ledger.jsonl` | the append-only Glassbox ledger |
| `LOCI_RTX_ENDPOINT` | `http://127.0.0.1:11434` | inference endpoint on the RTX 5060 Ti (Ollama) |
| `LOCI_ARC_ENDPOINT` | `http://127.0.0.1:11435` | inference endpoint on the Arc B70 Pro (llama.cpp SYCL) |

The parent folder of `LOCI_DB_PATH` is created on first use. Nothing is ever deleted from
either store: superseded facts are kept with a `valid_until` time, and cold facts stay on disk.

## 3. Store and search facts

```python
from loci_engine.storage import StorageEngine

storage = StorageEngine(db_path="memory.db")
storage.insert_fact("gpu_1", "hardware", "Workstation GPU is an Intel Arc B70 Pro with 32GB")
hits = storage.lexical_search("B70")          # BM25 over FTS5, ties broken by heat
print(hits[0]["id"])                          # gpu_1
```

To change a fact, write a new one that supersedes the old one. The old record is kept:

```python
storage.insert_fact("gpu_2", "hardware", "Workstation has two GPUs", supersedes_id="gpu_1")
```

`upsert_fact`, `get_current_fact`, `get_fact_at` and `get_fact_history` give versioned,
point-in-time access to keyed facts (paper 08).

## 4. Feed a conversation and recall with CARD

`SessionIngester` turns each chat turn into a memory item, then recalls with
**Category-Adaptive Recall Depth**: it classifies the question and picks how many items to
return and how to rank them.

```python
from loci_engine.session_ingester import SessionIngester
from loci_engine.storage import StorageEngine

ingester = SessionIngester(storage=StorageEngine(db_path="memory.db"), session_id="demo")
ingester.ingest_turn(role="user", content="I upgraded to the Arc B70")   # -> "demo_turn_0001"
result = ingester.recall_for_query("what GPU did the user mention")
result["archetype"]        # "information_extraction"
result["selected_items"]   # the recalled turns, best first
```

| Archetype | Depth K | Ranking |
|---|---|---|
| `information_extraction` | 5 | BM25 relevance |
| `knowledge_update` | 3 | heat, then recency |
| `multi_session_reasoning` | 10 | heat and temporal spread |
| `temporal_reasoning` | 7 | document date |

You can classify a question on its own with `CardRouter.classify_archetype(question)`.

## 5. Heat and tiers

Every item carries a heat score inside the open interval (0.05, 0.9999). Heat rises when an item
is used and decays hyperbolically when it is not, so it never reaches zero and is never
deleted. The tier decides where an item should live:

| Tier | Heat | Lives in | Decay τ |
|---|---|---|---|
| HOT | ≥ 0.80 | GPU VRAM working set | 1.25 days |
| MILD | ≥ 0.35 | host RAM (SymLinkPrev arena) | 1.75 days |
| COLD | < 0.35 | NVMe archive | 2.25 days |

Separately, **0.70 is the VRAM admission threshold** (`heat.VRAM_ADMISSION_THRESHOLD`): an item
with heat ≥ 0.70 may be loaded into VRAM even before it is formally HOT. The two numbers do
different jobs; see [ARCHITECTURE.md](ARCHITECTURE.md#heat-tiers-and-the-070-vs-080-question).

```python
from loci_engine import heat
heat.tier(0.82)                       # "hot"
heat.decay(0.82, elapsed=1.0, tau=1.25)
```

## 6. The Glassbox

The Glassbox is a shared, append-only ledger that every agent can read. Each entry is chained to
the previous one by SHA-256, so any edit to history breaks verification.

```python
from loci_engine import glassbox

glassbox.glassbox_learn("arc", "co-author", "HOT tier boundary is 0.80", category="principle")
glassbox.glassbox_recall("HOT tier")              # search what agents have learned
glassbox.glassbox_verify_chain()                  # {"valid": True, "entries": N, ...}
```

Categories: `observation`, `insight`, `correction`, `principle`, `discovery` and others listed
in `glassbox.py`. If `LOCI_DB_PATH` is set, entries are also mirrored into SQLite for search.

## MCP server

Any MCP client (Claude Code, Claude Desktop, an Ollama agent) can use LOCI as a tool server:

```bash
LOCI_DB_PATH=~/loci-memory-engine/context2.db python -m loci_engine.mcp_server
```

It speaks JSON-RPC 2.0 over stdio (MCP spec 2024-11-05). Example client config:

```json
{ "mcpServers": { "loci": {
    "command": "/path/to/LOCI-MEMORY-ENGINE/.venv/bin/python",
    "args": ["-m", "loci_engine.mcp_server"],
    "env": { "LOCI_DB_PATH": "/home/you/loci-memory-engine/context2.db" } } } }
```

The 34 tools:

| Group | Tools |
|---|---|
| Memory | `memory_search_lexical`, `memory_ingest_fact` |
| Glassbox | `glassbox_learn`, `glassbox_recall`, `glassbox_verify`, `glassbox_stats` |
| Ethics | `score_action` |
| Agents | `agent_register`, `agent_heartbeat`, `agent_send`, `agent_messages`, `agent_list`, `agent_feedback` |
| Sessions | `session_start`, `session_end`, `session_context`, `session_recall`, `session_history`, `prs_trend` |
| Feedback | `feedback_submit`, `feedback_list`, `feedback_respond`, `feedback_stats` |
| Patience | `patience_check`, `patience_enroll`, `block_escalate` |
| GPU | `gpu_status`, `gpu_allocate`, `gpu_complete`, `gpu_plan`, `gpu_route` |
| Node sync | `sync_node_status`, `sync_anti_entropy`, `sync_force`, `sync_add_peer` |

To run it as a service: `systemd/loci-mcp.service` (user unit, expects the repo at
`~/loci-memory-engine`).

The separate **coordination bus** (`coordination_bus/`) is an HMAC-authenticated task board for
several agents working on one codebase. Its MCP binding needs the `mcp` extra; see
[`architecture/SECURE-BUS.md`](../architecture/SECURE-BUS.md).

## 8. RAG over your documents

Needs the `rag` extra and a running [Ollama](https://ollama.com):

```bash
ollama pull nomic-embed-text && ollama pull llama3.2
python -m rag ingest --data-dir ./my-docs        # .pdf, .txt, .md
python -m rag query "What does paper 04 say about recall depth?"
```

Chunks are stored with sqlite-vec plus FTS5 and ranked by Reciprocal Rank Fusion. Each chunk has
its own heat, which decays with the canonical heat law and rises whenever a query returns it.

## 9. Running on several machines

`NodeSyncDaemon` keeps nodes in step: it polls the WAL for changes, sends CRDT deltas
(last-write-wins heat, lattice status, Glassbox entries) to peers, and uses Merkle trees to find
divergence. It never deletes on merge.

```bash
python -m loci_engine.node_sync_daemon            # peers come from ~/loci-memory-engine/config/nodes.env
systemctl --user start loci-sync                  # or as a service
```

## 10. Using LOCI from Arc

[Arc](https://github.com/arko-sanyal-loci/arc) is the local runtime that runs models on the
RTX 5060 Ti and Arc B70 Pro and uses LOCI as its memory. Point Arc at the same `LOCI_DB_PATH`
and Glassbox ledger, or connect it to the MCP server above. Arc's own README covers its setup.

## 11. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `sqlite3.OperationalError: unable to open database file` | The folder in `LOCI_DB_PATH` is not writable. Fixed for missing folders on 2026-11-19; check permissions. |
| `ImportError: cannot import name 'route_inference'` | You are on a commit between `acfc491` and the 2026-11-19 fix. Pull `main`. |
| `No module named 'mcp.server.fastmcp'` | `mcp` 2.x is installed. Use `pip install -e '.[mcp]'`, which pins `mcp<2`. |
| `ModuleNotFoundError: sqlite_vec` | Install the `rag` extra. |
| `glassbox_verify_chain()` returns `valid: False` | The ledger file was edited by hand or truncated. Restore it from a node that verifies. |
