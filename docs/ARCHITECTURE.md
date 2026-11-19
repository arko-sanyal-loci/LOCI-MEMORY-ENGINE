# Architecture overview

How the LOCI Memory Engine is put together, and where it sits in the Billo Tech stack.
For hands-on use, see the [User Guide](USER_GUIDE.md). For the research behind each part, see
[PAPERS.md](../PAPERS.md).

## The stack

```
                    The Glassbox
     shared, append-only, hash-chained knowledge compendium
                         ▲
                         │  learn · recall · verify
   agents & models ──►  LOCI Memory Engine  ◄──  Arc runtime
   (MCP / Python)        (this repo)              (local GPUs, chat UI)
                         │
          HOT (VRAM) · MILD (host RAM) · COLD (NVMe)
                  nothing is ever deleted
```

| Layer | Repo | Job |
|---|---|---|
| Memory engine | `LOCI-MEMORY-ENGINE` | store, heat, recall, ledger, sync, coordination bus |
| Runtime | [`arc`](https://github.com/arko-sanyal-loci/arc) | runs models on the RTX 5060 Ti (16 GB) and Arc B70 Pro (32 GB), uses LOCI as memory |
| Research | [`loci-card-papers`](https://github.com/arko-sanyal-loci/loci-card-papers) | the nine papers |

## Request path

```
agent ──► mcp_server.py (JSON-RPC 2.0, stdio)
              │
              ├─► session_ingester.py ──► storage.py (SQLite WAL + FTS5)
              │          │
              │          └─► card_router.py  classify question → depth K + ranking
              │
              ├─► glassbox.py      append-only SHA-256 chain (.jsonl + SQLite mirror)
              ├─► gpu_governor.py  GPU status, 5% safety margins, route_inference()
              └─► node_sync_daemon.py  WAL polling, CRDT deltas, Merkle divergence
```

## Modules by job

| Job | Modules |
|---|---|
| Storage and versioning | `storage.py`, `store.py`, `vectors.py` (RAG chunks with heat) |
| Heat law and tiers | `heat.py`, `thermal_gradient.py`, `slp_arena.py`, `dream_engine.py` |
| Retrieval | `card_router.py`, `session_ingester.py`, `session_continuity.py`, `rag/` |
| Shared knowledge | `glassbox.py`, `ledger/credit_ledger.jsonl` |
| Safety and ethics | `ethics.py`, `ethical_core.py`, `aethel_council.py`, `sanitizer.py`, `loop_guard.py`, `patience_protocol.py`, `ring_gate.py` |
| Agents | `agent_hub.py`, `agent_identities.py`, `feedback_platform.py`, `coordination_bus/` |
| Hardware | `gpu_governor.py`, `cold_start.py` |
| Interfaces | `mcp_server.py` (stdio MCP), `sovereign_bridge.py` (FastAPI, `bridge` extra) |
| Multi-node | `node_sync_daemon.py` |

## Heat

Heat follows three rules:

- **A1, evidence:** every past observation contributes `r·w / (1 + Δt/τ)`, so old evidence fades
  but never reaches zero.
- **A2, activation:** `H = α + (1 − α)(1 − e^(−βE))`.
- **A3, open interval:** `α < H < 1` always. `α = 0.05` is the "Constant of Hope" floor.

### Heat tiers and the 0.70 vs 0.80 question

A Dropbox sweep on 2026-11-19 found a 300-trial parameter sweep reporting that a HOT threshold of
0.70 works best, while the repo uses 0.80. The code already holds both numbers, for two jobs:

| Constant (`heat.py`) | Value | Job |
|---|---|---|
| `TIER_HOT_BOUNDARY` | 0.80 | label an item HOT (VRAM working set) |
| `TIER_MILD_BOUNDARY` | 0.35 | label an item MILD (host RAM) |
| `VRAM_ADMISSION_THRESHOLD` | 0.70 | admit an item into VRAM; this is the value the sweep tuned |

So the sweep's 0.70 is in use as the admission gate. What is still open is whether the HOT
*label* should also move to 0.70. That changes tier counts and decay τ for every item, so it is a
design decision for Arko, not a cleanup. `tests/test_e2e_smoke.py` pins all three values so any
change is deliberate.

## The Glassbox

Each entry stores `prev_hash` and `entry_hash = SHA-256(canonical JSON of the entry + prev_hash)`,
starting from `SHA-256("LOCI_GLASSBOX_GENESIS_2026")`. Anyone can re-walk the chain with
`glassbox_verify_chain()`. Entries are never edited; a correction is a new entry with
`supersedes_id`.

## Multi-node sync

Nodes (workstation, VPS, Mac mini) each run `NodeSyncDaemon`. Merges are CRDTs: heat is
last-write-wins by version vector, status is a lattice, Glassbox entries are a grow-only set.
Merges never delete. Merkle trees find which ranges differ.

## Coordination bus

`coordination_bus/` is a SQLite event log with HMAC-signed messages, task leases and a
review flow, so several agents (Claude, Codex, others) can work on one codebase without
last-write-wins. Payloads are data, never commands. See
[`architecture/SECURE-BUS.md`](../architecture/SECURE-BUS.md).
