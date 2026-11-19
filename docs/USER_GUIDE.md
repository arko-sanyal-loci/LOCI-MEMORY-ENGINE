# LOCI Memory Engine: user guide

This guide gets you from a fresh clone to an agent with persistent memory. For the design and the
maths, read the [README](../README.md) and the [papers](https://github.com/arko-sanyal-loci/loci-card-papers).

## 1. Install

```bash
git clone https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE
cd LOCI-MEMORY-ENGINE
python3 -m venv .venv
.venv/bin/pip install -e '.[dev,mcp,rag,bridge]'
.venv/bin/python -m pytest -q        # 228 tests, a few seconds
```

Extras: `mcp` (coordination-bus MCP server), `bridge` (FastAPI HTTP bridge), `rag` (Ollama
document pipeline), `dev` (pytest). The core engine has no third-party dependencies.

Two environment variables decide where memory lives:

| Variable | Default | What it holds |
|---|---|---|
| `LOCI_DB_PATH` | `~/loci-memory-engine/context2.db` | SQLite store: facts, heat, history |
| `LOCI_GLASSBOX_PATH` | next to the engine | Append-only, hash-chained learning ledger |

## 2. Store and recall facts

```python
from loci_engine.storage import StorageEngine

store = StorageEngine()
store.upsert_fact("user", "gpu", "Intel Arc B70 Pro, 32 GB")
store.get_current_fact("user", "gpu")
store.get_fact_history("user", "gpu")        # every earlier value, nothing deleted
```

Writing a new value for the same key supersedes the old one. The old record keeps a
`valid_until` timestamp, so `get_fact_at(...)` can answer "what was true on date X".

## 3. Feed a live conversation

```python
from loci_engine.session_ingester import SessionIngester

ingester = SessionIngester(storage=store, session_id="demo", actor_id="arc")
ingester.ingest_turn(role="user", content="I upgraded to the Arc B70 Pro, 32 GB")
result = ingester.recall_for_query("what GPU did the user mention")
result["archetype"]                          # 'information_extraction'
result["selected_items"][0]["canonical_text"]
```

CARD picks the recall depth from the kind of question:

| Archetype | Depth | Example |
|---|---|---|
| `information_extraction` | 5 | "what is X?" |
| `knowledge_update` | 3 | "what's the latest on X?" |
| `multi_session_reasoning` | 10 | "why did we decide X?" |
| `temporal_reasoning` | 7 | "earlier you said..." |

## 4. Share learning through the Glassbox

```python
from loci_engine.glassbox import glassbox_learn, glassbox_recall, glassbox_verify_chain

glassbox_learn(author_id="arc", role_tag="runtime", content="B70 runs the 32B target model")
glassbox_verify_chain()                      # {'valid': True, 'entries': N, ...}
```

Every entry is SHA-256 chained to the previous one. Any agent can read all of it, and tampering
breaks the chain.

## 5. Connect an agent over MCP

```bash
LOCI_DB_PATH=./memory.db .venv/bin/python -m loci_engine.mcp_server
```

### MCP tools

| Group | Tools |
|---|---|
| Memory | `memory_search_lexical`, `memory_ingest_fact`, `score_action` |
| Glassbox | `glassbox_learn`, `glassbox_recall`, `glassbox_verify`, `glassbox_stats` |
| Agents | `agent_register`, `agent_heartbeat`, `agent_send`, `agent_messages`, `agent_list`, `agent_feedback` |
| Sessions | `session_start`, `session_end`, `session_context`, `session_recall`, `session_history`, `prs_trend` |
| Feedback | `feedback_submit`, `feedback_list`, `feedback_respond`, `feedback_stats` |
| Patience | `patience_check`, `patience_enroll`, `block_escalate` |
| GPU | `gpu_status`, `gpu_allocate`, `gpu_complete`, `gpu_plan`, `gpu_route` |
| Sync | `sync_node_status`, `sync_anti_entropy`, `sync_force`, `sync_add_peer` |

The coordination bus has its own MCP server for multi-agent task leases and reviews:
`scripts/run_coordination_mcp.sh` (needs the `mcp` extra).

## 6. Run on more than one machine

`loci_engine/node_sync_daemon.py` merges memory between nodes with CRDTs and never deletes. The
systemd unit is `systemd/loci-sync.service`.

`scripts/ops/node_sync.sh` is a different tool: it keeps a **deployment** checkout identical to
`origin/main` and runs `git reset --hard` and `git clean -fd` when it drifts. Never point it at a
checkout you edit. It compares against `manifest.sha256`, so after changing `loci_engine/` run
`scripts/ops/update_manifest.sh` and commit the result.

## Heat thresholds

Heat lives in the open interval (0.05, 1.0). Tiers today:

| Tier | Heat | Hardware |
|---|---|---|
| HOT | ≥ 0.80 | VRAM working set |
| MILD | ≥ 0.35 | Host RAM |
| COLD | < 0.35 | NVMe |

`heat.VRAM_ADMISSION_THRESHOLD = 0.70` records the 300-trial sweep result (0.80 starved the HOT
set to 4 items and 60% recall). It is defined but not yet used by `storage.py`, and Arc's
tiering also classifies at 0.80. `thermal_gradient.py` uses its own 0.70 / 0.25 cut-offs and is
not wired in. Which threshold becomes the single source of truth is an open decision.

## 7. Where to go next

- [Arc](https://github.com/arko-sanyal-loci/arc): run this engine as the memory of a local model.
- [Papers](https://github.com/arko-sanyal-loci/loci-card-papers): the research behind each module.
- [`docs/REPO_STRUCTURE.md`](REPO_STRUCTURE.md): how the Billo Tech repositories fit together.
