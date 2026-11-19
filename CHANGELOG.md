# Changelog

All notable changes to LOCI-MEMORY-ENGINE are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased] — 2026-11-19

### Added

- **`loci_engine/vectors.py`** — Ported from the September engine. `VectorStore`
  wraps sqlite-vec + FTS5 with RRF(k=60) hybrid retrieval; chunk heat is
  persisted and reinforced on every retrieval; `decay()` and `reinforce()`
  drive thermal ageing between sessions.
- **`loci_engine/db.py`** — `open_db(path, timeout=30)` configures WAL mode and
  foreign-key enforcement; creates the parent directory automatically.
- **`loci_engine/provenance.py`** — `UserStated`, `resolve_trust`,
  `TRUST_WEIGHTS`, `DEFAULT_TRUST`; Bayesian prior over evidence provenance.
- **`loci_engine/tau_gate.py`** — Dynamic τ gate with MRR targets. Shapes the
  admission window based on result-score distribution, confidence history,
  query type, and temporal graph era. `GateDecision.passed` gates abstain
  when `RAG_ABSTAIN_ON_GATE=1`.
- **`loci_engine/compressor.py`** — `TfidfCompressor` reduces retrieved context
  with sentence-level TF-IDF scoring (no model dependency). The 8.89× claim
  was reported from an earlier session but has not been reproduced here;
  typical ratios under real workloads depend on chunk length and query overlap.
- **`loci_engine/value_bus.py`** — `ValueBus` implements typed-slot scoreboarding:
  declare → propose → commit forwarding with auto-commit on high confidence.
  `watch_stream()` and `route()` provide stream-aware integration.
- **`loci_engine/secrets_guard.py`** — `redact()` and `contains_secret()` scan
  for eight secret families (Anthropic, OpenAI, GitHub, AWS, Slack, Google,
  private keys, URL-embedded credentials). Called by `StorageEngine.insert_fact()`
  and `glassbox_learn()` before every write.
- **`research/trs_verification_package/`** — Sealed empirical benchmark suite
  (15 files, all matching `SHA256SUMS_SEALED`). Covers parameter sweeps,
  tie-breaker Monte Carlo, cross-domain validation, entropy ingestion, and
  polysemy/latency scaling.
- **`pyproject.toml`** — Package metadata and dependency groups (`[dev]`,
  `[mcp]`, `[bridge]`).
- **`tests/core/`** — 39 unit tests for heat, τ gate, compressor, value bus,
  secrets guard (including storage WAL and redaction integration).
- **`tests/integration/`** — Offline end-to-end pipeline tests (no model
  server required), sealed TRS package integrity check, and sweep
  reproducibility test.
- **`docs/decisions/0001-hot-threshold-0.70.md`** — Architecture Decision Record
  for the θ_HOT = 0.70 choice.
- **`archive/patches/`** — Three partially-applied ops patches preserved for
  reference (GPU naming, ethics layer, e2e ethics benchmark).
- **`archive/one-shot/`** — Historical one-shot setup scripts.
- **`scripts/ops/`** — Ops scripts relocated from root; `_nodes.sh` prelude
  sources `config/nodes.env` and validates required variables.
- **`config/nodes.env.example`** — Template for per-machine node config
  (replaces the previously tracked `config/nodes.env` which could contain
  host/IP details).

### Changed

- **`loci_engine/heat.py`** — `TIER_HOT_BOUNDARY = VRAM_ADMISSION_THRESHOLD = 0.7000`.
  The old 0.80 cutoff was never read by running code; this unifies the two
  constants and removes the silent split. See
  `docs/decisions/0001-hot-threshold-0.70.md`.
- **`loci_engine/storage.py`** — WAL journal mode; default alpha now
  `ALPHA_FLOOR` (0.05) instead of 0.01; `insert_fact` runs canonical text
  through `redact()` before storage.
- **`loci_engine/glassbox.py`** — Redacts content before hashing in
  `glassbox_learn()`.
- **`loci_engine/thermal_gradient.py`** — Thresholds sourced from `heat.py`
  constants (were previously inconsistent with `heat.py`).
- **`rag/pipeline.py`** — Rewritten with Guidance / Organisation / Efficiency
  docstring; dynamic τ gate on every retrieval; optional TF-IDF compression
  (`RAG_COMPRESS_RATIO`); optional abstain (`RAG_ABSTAIN_ON_GATE`).
- **`rag/config.py`** — Added `COMPRESS_RATIO`, `ABSTAIN_ON_GATE`; normalised
  `DB_PATH` / `CHROMA_DB_PATH` alias.
- **`mac-install/extractors/qsymprev_extractor.py`** (and `isymprev_extractor.py`,
  `loci_facts_extractor.py`, `scripts/loci_writer.py`) — API keys are now
  stored as `<redacted:{entity}:{sha8}>` placeholders, not plain text.
  Previous streams that saved raw keys should be rotated.
- **`.github/workflows/ci.yml`** — Switched from `unittest discover` to pytest;
  added matrix for Python 3.11 and 3.12; added TRS seal + verify step.
- **`.gitignore`** — Added `config/nodes.env`, `.env`, `*.env.local`.

### Removed

- Root-level duplicate patch files, stale `.bak` files, and scripts that had
  been moved to `scripts/` subdirectories.
- Hardcoded VPS hostnames and IPs from tracked files (see Security notes
  below).
- `gpu_governor.py` root duplicate (identical to `loci_engine/gpu_governor.py`).

### Security

- **qSympRev secret exposure (pre-existing):** Older extractor builds saved
  raw API keys to plain text files. This is now fixed (redaction to SHA-8
  fingerprints). **Any key ever processed by the old extractor should be
  considered exposed and rotated.**
- **VPS hostname / IP in git history:** `srv1775801.hstgr.cloud` and an
  associated IP were present in tracked files. They have been replaced with
  environment-variable references in the working tree, but they remain in git
  history (the repository is public). Consider rotating credentials or
  restricting access to that host.

### Known gaps / deferred work

- 8.89× TF-IDF compression ratio from an earlier session has not been
  reproduced here; treat it as unverified.
- τ-gate MRR targets are mathematically specified but coefficients have not
  been tuned against real retrieval sessions.
- `research/trs_verification_package/paper/` (PDF + LaTeX) was not imported —
  the PDF proxy-blocked during the original Dropbox sweep and the paper
  content carries IP considerations.
- billo-tech GitHub org profile / logo / repository archiving requires owner
  action (this session cannot act on the org).
