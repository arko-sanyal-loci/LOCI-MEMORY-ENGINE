# LOCI-MEMORY-ENGINE — Project Status

_Last updated: 2026-11-19 (cleanup: see [`docs/CLEANUP_2026-11-19.md`](docs/CLEANUP_2026-11-19.md)). This is the canonical, single repo. Everything
else under the arko-sanyal-loci org is either archived, duplicate, or
unrelated — see "Repo landscape" below._

## What's actually in here right now

| Area | What | Status |
|---|---|---|
| `loci_engine/` | Core engine: `thermal_gradient.py` (continuous Gaussian heat-gradient diffusion), `card_router.py` (archetype-based retrieval depth/strategy), `ethics.py` (post-hoc action scoring, trust mechanics, CommunicationHandshake/EthicsGate B5/B10/B19) | **Stable.** 160/160 tests passing before today's additions. |
| `coordination_bus/` | SQLite-backed inter-agent message bus: HMAC-authenticated, task leases, worktree-scoped workers, review/conflict flow, MCP server binding | **Merged today** from the separate `loci-coordination-bus` repo into this one, per the decision to consolidate into one repo. All bus tests pass with `mcp<2` installed (pinned in `pyproject.toml`). |
| `mac-install/` | 83 rescued files: `scripts/` (deception_scan.py, ethics_filter.py, injection_scan.py, sign_patch.py, values_admin.py, etc.), the identity/values markdown layer (values.md, honor.md, prime-directive.md, signature.md...), patches 1-13, `skills/loci-defense/` | **Rescued, not yet integrated.** Existed only in one password-protected email backup until today. Flat-copied in as-is; reorganizing it to actually plug into `loci_engine/` (e.g. ethics_filter.py vs ethics.py — do they overlap or conflict?) has NOT been done yet. |
| `ledger/`, `benchmarks/`, `config/`, `interface/`, `systemd/`, `architecture/` | Existing supporting infra | Untouched, assumed stable (part of the 160 passing tests). |
| Root-level clutter | Duplicate patches, `.bak` files and root copies removed; ops scripts moved to `scripts/ops/`; applied patches kept in `archive/` | **Done 2026-11-19.** |

## Repo landscape (org: arko-sanyal-loci)

- **`LOCI-MEMORY-ENGINE`** — canonical, this one. All future work goes here.
- `loci-memory-engine-1` — redirect README only. **Not archived yet** on GitHub (checked 2026-11-19); archive it in Settings.
- `loci-coordination-bus` / `LOCI-Coordinate-BUS` — coordination bus now merged into this repo. The two standalone repos are redundant now; archiving them is a GitHub action, blocked (see below).
- `loci-card-papers` (canonical, plural) vs `loci-card` / `loci-card-paper` (dead duplicates, same initial commit) — unrelated to the engine itself (publications), left alone.
- `docs` — not LOCI at all, an untouched fork of `github/docs`. Clutter, not debt.
- `arkosanyal/loci-engine` (different account) — intentional prior-art timestamp (Jul 2), not drift.

## Pushed (2026-11-18, after GitHub was connected)
1. EthicsGate/CommunicationHandshake patch
2. `mac-install/` rescue (83 files)
3. `coordination_bus/` merge
4. Archive redirects pushed to the 4 now-redundant repos: `loci-card`, `loci-card-paper` (→ `loci-card-papers`), `LOCI-Coordinate-BUS`, `loci-coordination-bus` (→ `LOCI-MEMORY-ENGINE`)

All of the org's LOCI repos now point to exactly one canonical place: this repo.

## Not yet done
- Reorganize `mac-install/` so its scripts actually integrate with `loci_engine/` rather than sitting as a flat copy (check for overlap/conflict between e.g. `mac-install/scripts/ethics_filter.py` and `loci_engine/ethics.py`)
- ~~Install `fastmcp`~~ The MCP test needed `mcp<2` (FastMCP was renamed in mcp 2.x). Now pinned in `pyproject.toml`; all 173 tests pass.
- Future, explicitly deferred: Glass Box Compendium integration (multi-agent perspective resolution via coordination_bus + the heat/stream tie-break mechanism validated earlier today against real session data)
