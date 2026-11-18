<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="brand/billo-tech-logo-dark.svg">
  <img alt="Billo Tech" src="brand/billo-tech-logo-light.svg" width="520">
</picture>

# LOCI Memory Engine

**Heat-tiered, goal-conditioned memory and context orchestration for LLM agents.**
The substrate that every LOCI module plugs into, and the foundation of **The Glassbox**, a shared,
transparent knowledge compendium for agents and AI models.

[![CI](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/actions/workflows/ci.yml/badge.svg)](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?style=flat-square)
![Status: active](https://img.shields.io/badge/status-active-4F46E5?style=flat-square)
[![Billo Tech](https://img.shields.io/badge/Billo%20Tech-LOCI-06B6D4?style=flat-square)](https://github.com/arko-sanyal-loci)

</div>

---

## What it is

LOCI gives an agent a memory that behaves like a working mind rather than a flat vector store.
Every fact carries a **heat** score that decays over time by tier, rises when it is used, and
spreads to its neighbours. Hot facts stay close to the model; cold facts are never deleted, only
moved further away. Retrieval depth adapts to the kind of question being asked (**CARD**), and
every agent's learnings land in an append-only, hash-chained ledger that every other agent can
read (**The Glassbox**).

This is the **single canonical repository** for the engine. Earlier split repos have been
consolidated here; see [Repository map](#repository-map).

## Architecture at a glance

```
                ┌──────────────────────────── The Glassbox ────────────────────────────┐
                │  append-only, hash-chained shared learning ledger (glassbox.py)      │
                └──────────────▲──────────────────────────────────────▲────────────────┘
                               │ learn / recall                       │ sync
   Agents & models ──► MCP server (mcp_server.py) ──► Governance gate (governance.py, ethics.py)
                               │
             ┌─────────────────┼──────────────────────────┬────────────────────────┐
             ▼                 ▼                          ▼                        ▼
      Heat & tiers       CARD router              Session continuity        Coordination bus
   heat.py              card_router.py           session_continuity.py      coordination_bus/
   thermal_gradient.py  loop_guard.py            session_ingester.py        (HMAC, leases, MCP)
             │
             ▼
   Storage: HOT (VRAM) · MILD (host RAM) · COLD (NVMe, context2.db via storage.py / store.py, never deleted)
```

## Repository layout

| Path | What lives there |
|---|---|
| [`loci_engine/`](loci_engine) | The core package: heat and thermal gradient, CARD router, storage, Glassbox ledger, governance and ethics layer, session continuity, loop guard, MCP server, GPU governor, node sync. |
| [`coordination_bus/`](coordination_bus) | Secure, local-first inter-agent message bus (HMAC-authenticated, task leases, review and conflict flow) with an MCP binding. Merged in from the former `loci-coordination-bus` repo. |
| [`agents/`](agents) | 32-agent workspace (16 `alpha_blueprint` + 16 `beta_runtime`). See [`agents/COORDINATION.md`](agents/COORDINATION.md) and [`agents/PHASES.md`](agents/PHASES.md). |
| [`architecture/`](architecture) | Design docs: port registry, secure bus spec. |
| [`config/`](config), [`systemd/`](systemd) | Model files, GPU allocation, reverse-proxy configs, service units. |
| [`tests/`](tests) | Unit tests for the engine and the coordination bus. |
| [`benchmarks/`](benchmarks) | End-to-end benchmarks (e.g. the unified ethics layer). |
| [`mac-install/`](mac-install) | Rescued identity, values and defence scripts. Copied in as-is, **not yet integrated** with `loci_engine/`. |
| [`brand/`](brand) | Billo Tech logo assets (SVG). |
| [`docs/`](docs) | Project documentation, including the [repository structure plan](docs/REPO_STRUCTURE.md). |
| [`STATUS.md`](STATUS.md) | Current build status and open work. |

## Quick start

```bash
git clone https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE.git
cd LOCI-MEMORY-ENGINE
python3 -m venv .venv && source .venv/bin/activate
pip install pytest

# run the engine test suite
python -m unittest discover -s tests -p "test_*.py"

# run the coordination bus tests (the MCP test needs `pip install fastmcp`)
python -m pytest tests/coordination_bus
```

As of 2026-11-18 on `main`: 129/129 engine tests pass, and 10/11 coordination bus tests pass
(the one failure is `fastmcp` not being installed, not a code fault).

## Core ideas

| Concept | In one line | Module |
|---|---|---|
| **Heat tiers** | Heat lives in the open interval (0.05, 0.9999): it decays by tier, warms on use, and never reaches zero. HOT ≥ 0.80 (VRAM working set), MILD ≥ 0.35 (host RAM), else COLD (NVMe ledger). Nothing is deleted. | `heat.py`, `thermal_gradient.py` |
| **CARD** | Category-Adaptive Recall Depth: retrieval depth and ranking strategy depend on the question type. | `card_router.py` |
| **SymLinkPrev nodes** | Compact 20-byte memory nodes (locator, domain, heat, trust, lineage) packed into 64-byte cache-line slots. | `slp_arena.py`, `store.py` |
| **Loop guard** | A circuit breaker that halts before re-processing an identical goal in a loop. | `loop_guard.py` |
| **The Glassbox** | Every agent's learnings in one append-only, hash-chained ledger, readable by all. | `glassbox.py` |
| **Governance** | A single gate for ethics, trust and communication handshakes before actions propagate. | `governance.py`, `ethics.py`, `ring_gate.py` |

The research behind these ideas is published in
[**loci-card-papers**](https://github.com/arko-sanyal-loci/loci-card-papers).

## Repository map

| Repository | Role |
|---|---|
| **[LOCI-MEMORY-ENGINE](https://github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE)** | Canonical engine (this repo). |
| **[arc](https://github.com/arko-sanyal-loci/arc)** | Arc, the local AI runtime and LOCI co-author: runs a model on local GPUs with LOCI memory. |
| **[loci-card-papers](https://github.com/arko-sanyal-loci/loci-card-papers)** | The published LOCI and CARD research papers. |
| `loci-memory-engine-1`, `loci-coordination-bus`, `LOCI-Coordinate-BUS`, `LOCI-Card`, `LOCI-CARD-PAPER` | Archived. Each README redirects to its canonical home. |

## Contributing

Work happens on short-lived branches with a pull request into `main`. CI runs the test suite on
every pull request. See [`docs/REPO_STRUCTURE.md`](docs/REPO_STRUCTURE.md) for branch naming.

## License

See [`LICENSE.md`](LICENSE.md). © 2026 Arko Sanyal, Billo Tech.
