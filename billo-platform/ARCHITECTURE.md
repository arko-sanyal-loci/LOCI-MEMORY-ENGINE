# Billo & LOCI Unified System Architecture

## 1. System Overview & Deployment Topology

The Billo & LOCI platform operates across a hybrid compute topology that partitions heavy machine learning inference from persistent context management and edge routing:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       LOCAL GPU WORKSTATION (Windows 11)                   │
│  Hardware: Intel i7-12700K | NVIDIA RTX 3080 Ti | 32GB DDR5                │
│  Codebase: F:\Billo\                                                        │
│  SQLite: F:\Billo\data\context2.db                                          │
│  Local Ollama: qwen2.5-coder:14b on http://localhost:11434                  │
│                                                                             │
│  Exclusive GPU Endpoints (Guarded by GPU_LOCK):                             │
│   • /refine               ComfyUI image pipeline + Ollama 14b               │
│   • /forge/*              Ollama 14b code generation & Git patches          │
│   • /ops/comfyui/restart  Windows PowerShell process recycler               │
└──────────────────────────────────────┬──────────────────────────────────────┘
                                       │ SSH Tunnel: 127.0.0.1:11435 -> VPS:11434
                                       ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                 HOSTINGER VPS (Ubuntu 24.04 LTS, Docker / Nginx)            │
│  Host: configured with BILLO_VPS_HOST                                      │
│  Domains: billo.tech, arc.billo.tech                                        │
│  VPS Ollama: qwen2.5:3b on http://127.0.0.1:11434 (Internal loopback only)  │
│                                                                             │
│  Lightweight CPU / VPS-Safe Endpoints:                                      │
│   • /v1/compress          VPS Ollama 3b (timeout 60s) + heuristic fallback  │
│   • /v1/context/query     SQLite search + CER token efficiency audit        │
│   • /v1/context/slice     Read-only temporal era slices                     │
│   • /v1/context/entities  Read-only entity catalog                          │
│   • /v1/context/handover  LOCI compact tags (~560 tokens, 61% reduction)   │
│   • /v1/symbols           CPU AST/Regex code symbol extraction              │
│   • /v1/scratch/*         Fast key-value JSON persistence                   │
│   • /ops/optimize         Task routing (local/vps/forge/claude)             │
│                                                                             │
│  Hybrid Endpoints:                                                          │
│   • /ops/rnd              Prefers Ollama 14b GPU, falls back to VPS 3b      │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Bug Resolutions & Engineering Standards

### Bug #10 (Critical): SQLite "database is locked" Under Async Load
* **Problem**: In FastAPI's async execution context, concurrent writes to `token_efficiency_log` and `compress_log` collided with SQLite's default rollback journal, creating `sqlite3.OperationalError: database is locked`.
* **Resolution**: All database connection instantiations (`loci/engine.py`, `billo/app.py`, `Workers/learning_loop.py`) strictly execute:
  ```sql
  PRAGMA journal_mode = WAL;
  PRAGMA synchronous = NORMAL;
  PRAGMA busy_timeout = 5000;
  PRAGMA foreign_keys = ON;
  ```
  WAL (Write-Ahead Logging) allows concurrent readers to proceed uninterrupted while a single writer commits, and `busy_timeout = 5000` queues transient locks rather than raising immediate exceptions.

### Bug #9: Hot-Path Dynamic Import Overhead
* **Problem**: Inside per-request query handlers, `from loci.efficiency import query_hash as _qhash` was executed dynamically on every incoming request, introducing module lookup and lock acquisition overhead.
* **Resolution**: Imported `query_hash` at module scope across all entry points (`Workers/learning_loop.py` and `billo/app.py`).

### Bug #8: Inflated Context Efficiency Ratio (CER) Baseline
* **Problem**: Baseline token calculation previously used `n_hits * 4.0`. Using the number of *returned hits* rather than *entities scanned* artificially penalized high-precision queries and produced inaccurate CER numbers.
* **Resolution**: Rewritten in `loci/efficiency.py`:
  $$\text{Baseline Cost} = \text{Total Raw Entities Scanned} \times 4.0$$
  $$\text{CER} = \frac{\text{Baseline Cost}}{\text{LOCI Effective Cost}}$$
  This produces genuine, verifiable efficiency multiples (e.g. 5–10×) against raw brute-force token scans.

### Bug #7: In-Memory Entity Occurrence Accumulator Loss
* **Problem**: The `_occurrences` dictionary risked resetting when `index()` was invoked across multiple chunked batches.
* **Resolution**: `LociEngine.index()` preserves existing entity occurrences across successive calls by default, only resetting when `reset_accumulator=True` is explicitly passed.

### Bug #6: Thread-Local SQLite Connection Leaking
* **Problem**: Connections stored in `threading.local()` were never explicitly closed when worker threads exited.
* **Resolution**: Implemented explicit connection tracking in `LociEngine` with a registry lock and cleanup methods (`close_thread_connection()` and `close_all()`).

### PowerShell `$PID` Reserved Variable Gotcha
* **Problem**: In Windows PowerShell, `$PID` is a reserved variable containing the current shell's process ID. Calling `Kill $PID` crashes the terminal window.
* **Resolution**: `Start-Billo.ps1` strictly uses `Stop-Process -Name python -Force -ErrorAction SilentlyContinue`.

---

## 3. LOCI Memory Architecture & Pricing Schedule

LOCI normalizes memory into a 3-tier temporal decay hierarchy:
* **Far Era**: System initialization, core baseline credentials, architectural constraints.
* **Mid Era**: Completed bug fixes, resolved tickets, infrastructural migrations.
* **Near Era**: Active work items, real-time context handovers, immediate sprint goals.

### Token Pricing Weights (`loci/efficiency.py`)
| Lookup Strategy | Cost (Tokens) | Multiplier vs Full Scan | Description |
|---|---|---|---|
| `by_tag_number` | 0.25 | 16.0× | Numeric entity pre-filtered via tag index |
| `by_tag` | 0.35 | 11.4× | Non-numeric entity matched via tag index |
| `by_value_number` | 0.50 | 8.0× | Direct numeric value match |
| `by_value` | 0.75 | 5.3× | Direct string value match |
| `by_hint` | 1.00 | 4.0× | Context hint occurrence match |
| `full_scan` | 4.00 | 1.0× | Raw brute-force full context scan (Baseline) |

### Handover Protocol Format
Instead of passing 4,000+ raw transcript tokens, `GET /v1/context/handover/{session_id}` emits structured tag blocks:
```text
[session:session_001 | era:2026-09-06 | turns:50]
[entity:🔗 learning_loop.py | type:file | era:near | hits:14]
[entity:🔗 _compress_via_vps | type:def | era:near | hits:8]
[entity:GPU_LOCK | type:constant | era:mid | hits:4]
[era:far] Infrastructure stabilization, tunnel setup, and security lock.
[era:mid] Bug fixes (#6, #8, #9, #10) applied; TIMEOUT_VPS_COMPRESS->60s.
[era:near] Real-time compression active, hybrid /ops/rnd live.
```
**Outcome**: ~560 tokens per handover, representing a >60% token footprint reduction.
