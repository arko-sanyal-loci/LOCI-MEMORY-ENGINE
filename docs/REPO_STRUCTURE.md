# Billo Tech repository structure

_Updated 2026-11-19. Supersedes the 2026-11-18 draft._

## Active repositories (keep)

```
arko-sanyal-loci
├── LOCI-MEMORY-ENGINE   engine, coordination bus, Glassbox ledger, RAG pipeline
├── arc                  local runtime and LOCI co-author (uses the engine)
└── loci-card-papers     the published LOCI / CARD papers
```

## Redirect repositories (archive)

Each one has a README that points to its canonical home. Archiving makes them read-only and keeps
their history; nothing is deleted.

| Repository | Last commit | Canonical home | Why it is redundant |
|---|---|---|---|
| `loci-memory-engine-1` | 2026-11-19 (README only) | `LOCI-MEMORY-ENGINE` | Fork of `arko-sanyal/loci-memory-engine`. RAG pipeline and vector store ported. Its README lists the design specs and installer that stay readable there. |
| `loci-coordination-bus` | 2026-11-18 (README only) | `LOCI-MEMORY-ENGINE/coordination_bus/` | Code merged 2026-11-18 |
| `LOCI-Coordinate-BUS` | 2026-11-18 (README only) | `LOCI-MEMORY-ENGINE/coordination_bus/` | Older copy of the same bus |
| `LOCI-Card` | 2026-11-18 (README only) | `loci-card-papers` | Byte-identical copy of the papers |
| `LOCI-CARD-PAPER` | 2026-11-18 (README only) | `loci-card-papers` | Byte-identical copy of the papers |
| `docs` | 2026-11-04 | none | Unmodified fork of `github/docs`, not LOCI |

The September originals under `arko-sanyal` (`loci-memory-engine`, `loci-coordination-bus`,
`loci-card-papers`, last pushed 2026-09-10/11) are the upstreams of the forks above. They need a
README pointing here and then archiving, from that account.

## Organization

`billo-tech` exists as a GitHub organization. Its profile README lives in a repository named
`.github` at `profile/README.md`; the content is in [`docs/profile/README.md`](profile/README.md).
Moving the three active repositories into `billo-tech` is optional: GitHub redirects old URLs,
but clones and hard-coded links should be updated afterwards.

## Conventions

- One job per repository. New engine work goes to `LOCI-MEMORY-ENGINE`, runtime work to `arc`.
- `main` is the only long-lived branch. Feature branches merge by pull request and are deleted.
- After changing `loci_engine/`, run `scripts/ops/update_manifest.sh` (CI enforces it).
