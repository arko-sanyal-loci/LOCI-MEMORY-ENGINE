# LOCI Unified Port Registry & Architecture Unification Plan

**Date:** 2026-11-01
**Author:** Arko Sanyal + Claude Opus 4.6
**Status:** Active — consolidating diverging engines into one unified system

---

## 1. PORT REGISTRY: Architecture Docs vs. Current Reality

### From BIILOTECH System Architecture (Oct 4, 2026)
| Port | Service | Status |
|------|---------|--------|
| MCP stdio/SSE | LOCI Daemon & Reverse Proxy Middleware | **Partially implemented** — MCP server exists (30 tools) but runs via stdio, not SSE |
| 7890 | Forecast Director Console (live KV-cache, compression ratios) | **NOT RUNNING** |
| /dev/shm | POSIX shared memory IPC ring buffer (zero-copy) | **NOT IMPLEMENTED** — storage uses SQLite WAL instead |

### From Forge/LOCI Reactivation Guide (Oct 24, 2026)
| Port | Service | Status |
|------|---------|--------|
| 8768 | LOCI loopback server | **NOT RUNNING** — superseded by sovereign engine on 8000 |
| 8080/sse | Spark execution engine (MCP connector) | **NOT RUNNING** — Gemini Spark suspended |
| 9443 | Portainer (Docker management on VPS) | **VPS unreachable** — SSH key needs re-setup |
| 11435→11434 | SSH tunnel (VPS→workstation Ollama) | **NOT ACTIVE** — VPS SSH broken |

### From v2.2 Cold-Start Boot Script (Oct 24, 2026)
| Component | Status |
|-----------|--------|
| /dev/shm/loci_arena | **NOT CREATED** |
| /opt/loci/data/context2.db | **DIFFERENT PATH** — actual: ~/loci-memory-engine/context2.db |
| ZE_AFFINITY_MASK=0 (Intel compute) | **NOT SET** — compute runtime not installed |
| OLLAMA_MAX_LOADED_MODELS=2 | **NOT SET** — Ollama using defaults |

### Currently Running (Nov 1, 2026)
| Port | Service | Binding | PID | Notes |
|------|---------|---------|-----|-------|
| 8000 | Sovereign Engine + LOCI Bridge | 0.0.0.0 | uvicorn 64307 | **THE ACTUAL UNIFIED GATEWAY** |
| 11434 | Ollama | 127.0.0.1 only | 45201 | Localhost-only — proxied via :8000/loci/ollama |
| 22 | SSH | 0.0.0.0 | sshd | Laptop connected |

### Console/Laptop (.149)
| Port | Service | Status |
|------|---------|--------|
| — | No services exposed | Laptop SSH'd into workstation but runs nothing reachable |

### VPS (srv1775801.hstgr.cloud)
| Port | Service | Status |
|------|---------|--------|
| — | Unknown | Alive (56ms ping) but SSH key denied |

---

## 2. THE DIVERGENCE PROBLEM

Multiple architecture documents describe different port layouts and service locations.
The old Forge/LOCI architecture had services fragmented across:
- Port 8768 (LOCI loopback)
- Port 8080 (Spark SSE)
- Port 7890 (Forecast Director)
- Port 9443 (Portainer on VPS)
- SSH tunnels bridging VPS↔workstation

Meanwhile, the workstation now runs a SINGLE unified gateway on port 8000 that
already consolidates:
- Sovereign Architecture (ethics, DIPL, CARD router, verify-action)
- Hark & Carrot (audio ingest, behavioral events)
- LOCI MCP Bridge (30 tools: agents, sessions, Glassbox, feedback, patience, GPU, memory)
- Ollama proxy (inference through the sovereign gate)

**The sovereign engine on port 8000 IS the unification point.**

---

## 3. UNIFIED ARCHITECTURE: NGINX REVERSE PROXY

One entry point. All traffic routes through nginx, which forwards to the
sovereign engine. The sovereign engine is the single brain — all tools,
all agents, all ethics, all Glassbox transparency.

```
                    ┌──────────────────────────────────────────┐
                    │           NGINX REVERSE PROXY             │
                    │         Port 80 / 443 (TLS)               │
                    │                                          │
                    │  /                → Sovereign Dashboard   │
                    │  /heat/api/v1/*   → Sovereign Telemetry   │
                    │  /loci/*          → LOCI Bridge (30 tools)│
                    │  /api/docs        → FastAPI Swagger       │
                    │                                          │
                    │  Subnet: 192.168.10.0/24                 │
                    │  External: billo.tech (VPS mirror)        │
                    └──────────────┬───────────────────────────┘
                                   │
                    ┌──────────────▼───────────────────────────┐
                    │     SOVEREIGN ENGINE (uvicorn :8000)       │
                    │                                          │
                    │  ┌─ Sovereign Core ──────────────────┐   │
                    │  │  Ethics / DIPL / CARD Router       │   │
                    │  │  Verify-Action guardrail            │   │
                    │  │  Hark (audio) & Carrot (habits)     │   │
                    │  └───────────────────────────────────┘   │
                    │                                          │
                    │  ┌─ LOCI Bridge (30 REST routes) ────┐   │
                    │  │  Agent Hub (6)     Session (5)      │   │
                    │  │  Glassbox (4)      Feedback (4)     │   │
                    │  │  Patience (3)      GPU Gov (4)      │   │
                    │  │  Memory (2)        Ollama proxy (1) │   │
                    │  │  System status (1)                  │   │
                    │  └───────────────────────────────────┘   │
                    └──────────────┬───────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                    │
    ┌─────────▼──────┐  ┌─────────▼──────┐  ┌─────────▼──────┐
    │   Ollama        │  │  context2.db    │  │  Glassbox      │
    │   :11434        │  │  SQLite WAL     │  │  JSONL ledger  │
    │   (localhost)   │  │  FTS5 + heat    │  │  SHA-256 chain │
    │                 │  │  16 active items│  │  19 entries     │
    │  loci-agent-14b │  │  5 namespaces   │  │  5 authors      │
    │  loci-agent-7b  │  │                 │  │                 │
    │  qwen2.5:14b    │  │                 │  │                 │
    │  qwen2.5:7b     │  │                 │  │                 │
    └────────────────┘  └────────────────┘  └────────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │                    GPU COMPUTE                            │
    │                                                          │
    │  NVIDIA RTX 5060 Ti          Intel Arc B70 Pro Sparkle   │
    │  16 GB VRAM, CUDA 13.2       32 GB VRAM, Battlemage G31  │
    │  Safe: 171W / 85°C           Safe: 313W / 90°C           │
    │  Status: Active, 39°C        Status: D3hot (pending)     │
    │  Models: loci-agent-14b,     Pending: compute runtime    │
    │          loci-agent-7b       needs intel-opencl-icd       │
    └──────────────────────────────────────────────────────────┘
```

### Port Consolidation Map (Old → Unified)

| Old Port | Old Service | Unified Location |
|----------|-------------|------------------|
| 8768 | LOCI loopback server | **:8000/loci/** (bridge) |
| 8080 | Spark execution engine | **:8000/loci/ollama/generate** (local models replace Spark) |
| 7890 | Forecast Director Console | **:8000/** (sovereign dashboard, to be expanded) |
| 9443 | Portainer (VPS Docker) | **VPS**: reinstall after SSH fixed |
| 11434 | Ollama (direct) | **:8000/loci/ollama/** (proxied, no direct access needed) |
| 11435→11434 | SSH tunnel VPS→workstation | **:8000/loci/ollama/** (VPS connects to workstation bridge) |

### Nodes After Unification

| Node | Role | Entry Point |
|------|------|-------------|
| Workstation (.181) | Primary compute, sovereign engine | :80 (nginx) → :8000 (uvicorn) |
| Laptop (.149) | Console, operator interface | SSH + http://192.168.10.181/loci/* |
| VPS (billo.tech) | Mirror, external access, subnet feedback | :80 (nginx) → reverse proxy to workstation or local mirror |

---

## 4. ACTIONS REQUIRED

### Immediate (no sudo needed)
- [x] Sovereign engine running with LOCI bridge (30 routes)
- [x] All 4 agents registered and communicating
- [x] GPU governor with safety margins
- [x] Ollama proxied through sovereign gate
- [ ] Expand sovereign dashboard to include Forecast Director metrics

### Requires sudo (workstation)
- [ ] `sudo apt-get install -y nginx`
- [ ] Configure nginx reverse proxy (:80 → :8000)
- [ ] `sudo apt-get install -y intel-opencl-icd intel-gpu-tools` (Arc B70 Pro compute)
- [ ] `sudo usermod -aG render,video arko-sanyal` (GPU access)

### Requires SSH key fix (VPS)
- [ ] Re-add SSH key to VPS
- [ ] Install nginx on VPS for billo.tech external mirror
- [ ] Set up VPS→workstation reverse proxy or local engine mirror
- [ ] Restore Portainer on :9443

### Requires interactive auth
- [ ] `ssh-add ~/.ssh/id_ed25519` — GitHub push (passphrase)
