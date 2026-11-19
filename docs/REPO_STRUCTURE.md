# Billo Tech repository structure

_Audit date: 2026-11-18. Account: `arko-sanyal-loci` (a GitHub **user** account, not an organization)._

This document records what exists today, what the target layout is, and the remaining steps.
Steps marked **(owner)** need Arko to act in GitHub settings, because they cannot be undone
from a pull request.

## 1. Audit: what exists today

| Repository | Type | Default branch | State | Verdict |
|---|---|---|---|---|
| `LOCI-MEMORY-ENGINE` | source | `main` | Active. Engine, coordination bus, agents workspace. README was a two-line stub. | **Keep: canonical engine.** README rewritten. |
| `arc` | source | `main` | Active. Arc runtime (FastAPI, GPU offload, chat UI). Good README. | **Keep: canonical runtime.** Footer links updated to canonical repos. |
| `loci-card-papers` | fork of `arko-sanyal/loci-card-papers` | `master` | Active. Nine published papers. README linked to the old `arko-sanyal` account. | **Keep: canonical papers.** Links fixed. |
| `loci-memory-engine-1` | fork of `arko-sanyal/loci-memory-engine` | `main` | README already redirects to `LOCI-MEMORY-ENGINE`. RAG pipeline ported. | **Archive (owner).** |
| `loci-coordination-bus` | fork of `arko-sanyal/loci-coordination-bus` | `master` | README already redirects. Code merged into `LOCI-MEMORY-ENGINE/coordination_bus/`. | **Archive (owner).** |
| `LOCI-Coordinate-BUS` | source | `master` | README already redirects. Stale predecessor of the bus. | **Archive (owner).** |
| `LOCI-Card` | source | `master` | README already redirects. Byte-identical duplicate of the papers. | **Archive (owner).** |
| `LOCI-CARD-PAPER` | source | `master` | README already redirects. Byte-identical duplicate of the papers. | **Archive (owner).** |
| `docs` | fork of `github/docs` | `main` | Untouched GitHub Docs fork. Not LOCI. | **Delete or archive (owner).** Pure clutter. |

Archiving is preferred over deleting for the five LOCI duplicates: it keeps their history and
redirect READMEs readable while making them read-only and hiding them from the active list.

## 2. Target layout

Three active repositories, one job each:

```
arko-sanyal-loci (Billo Tech)
├── LOCI-MEMORY-ENGINE   engine, coordination bus, Glassbox ledger, agents workspace
├── arc                  local AI runtime and LOCI co-author (consumes the engine)
└── loci-card-papers     published research (LOCI, CARD)
```

Plus, once created, the profile repository:

```
└── arko-sanyal-loci     profile README shown at github.com/arko-sanyal-loci
```

Because `arko-sanyal-loci` is a user account, the profile README lives in a repository named
exactly `arko-sanyal-loci` (an organization would use a `.github` repository instead). The ready
content is in [`docs/profile/README.md`](profile/README.md).

### Optional: a real `billo-tech` GitHub organization

If Billo Tech should appear as a company rather than a person, create a free GitHub organization
(for example `billo-tech`) and transfer the three active repositories into it. GitHub redirects
old URLs after a transfer, but clones, CI badges and any hard-coded `arko-sanyal-loci/...` links
should still be updated afterwards. This is a bigger, outward-facing change, so it is listed as a
choice rather than a step.

## 3. Naming conventions

- Repository names: one casing style. The canonical repos currently mix `LOCI-MEMORY-ENGINE`
  (upper) and `loci-card-papers` (lower). Renaming `LOCI-MEMORY-ENGINE` to `loci-memory-engine`
  would make this consistent; GitHub keeps a redirect from the old name. **(owner, optional)**
- Branches: `main` is the only long-lived branch. Feature work uses
  `<area>/<short-description>` (e.g. `engine/heat-rescale`, `arc/hybrid-inference`), merged by
  pull request and then deleted.
- `loci-card-papers` uses `master`; switching its default to `main` would match the other two.
  **(owner, optional)**

## 4. Branch cleanup in LOCI-MEMORY-ENGINE

| Branch | Notes | Proposed action |
|---|---|---|
| `main` | Canonical. | Keep. |
| `reconcile` | Pending merge into `main` (open question about the cold storage substrate). | Decide and merge or close; do not delete until resolved. |
| `arc/hybrid-inference-design` | Design work for Arc. | Merge into `arc` or `main` if still wanted, then delete. |
| `claude/gallant-cerf-ga088c` | Old agent session branch. | Review, then delete. |
| `cursor/learning-loop-cycle-3012` | Old agent session branch. | Review, then delete. |

`.github/workflows/ci.yml` also runs on pushes to `reconcile`; drop that once `reconcile` is merged.

## 5. Root-level cleanup in LOCI-MEMORY-ENGINE (not done yet, needs sign-off)

- Seven `000N-*.patch` files at the root, four of them byte-identical duplicates (`_1`, `_2`
  suffixes). Patch 0003 is fully applied on `main`; 0001 and 0002 no longer reverse cleanly, so
  they were applied and then edited further, or only partly applied. Proposed: delete the four
  duplicates now, and delete the three originals once someone confirms 0001 and 0002 landed.
- About ten operational scripts at the root (`harden_vps.sh`, `node_sync.sh`,
  `push_station0.sh`, `sync_to_remote.sh`, `gpu_governor.py`, ...). Proposed: move them to
  `scripts/ops/`. This touches paths that systemd units or local cron jobs may reference, so it
  should be checked on the machines first.
- Two `*.stale-vulkan-*.bak` files in `architecture/` and `loci_engine/`. Proposed: delete.
- `LICENSE.md` still contains the placeholder "[Specify your license here ...]". A license
  needs to be chosen. **(owner)**

## 6. Checklist

- [x] Canonical engine README
- [x] Billo Tech logo (`brand/`)
- [x] Papers README links point at canonical repos
- [x] Arc README links point at canonical repos
- [x] Profile README drafted (`docs/profile/README.md`)
- [ ] **(owner)** Create the `arko-sanyal-loci/arko-sanyal-loci` repository for the profile README
- [ ] **(owner)** Archive the five redirect repos; delete or archive the `docs` fork
- [ ] **(owner)** Choose a license
- [ ] Branch cleanup in `LOCI-MEMORY-ENGINE`
- [ ] Root-level cleanup in `LOCI-MEMORY-ENGINE`
