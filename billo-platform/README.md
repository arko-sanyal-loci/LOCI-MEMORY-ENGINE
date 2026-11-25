# Billo & LOCI Unified Deployment Repository

Production-grade deployment codebase unifying the **LOCI Persistent Memory Engine** and the **Billo Autonomous Orchestration System** across local GPU workstations and Virtual Private Server (VPS) infrastructure.

---

## Directory Structure

```text
billo_loci_unified/
├── ARCHITECTURE.md            # Deep-dive architecture, bug fixes & topology
├── README.md                  # System setup and operational documentation
├── requirements.txt           # Python dependency specifications
├── .env.example               # Environment variables template
├── data/                      # Persistent SQLite data directory (context2.db)
├── loci/                      # LOCI Memory Engine Core
│   ├── __init__.py            # Package exports
│   ├── engine.py              # LociEngine: WAL mode, ring buffers, indexing
│   ├── efficiency.py          # CER metrics, token weighting, Bug #8 resolution
│   └── schema.sql             # Complete context2.db SQLite DDL schema
├── Workers/                   # Background Task Daemons
│   ├── __init__.py
│   └── learning_loop.py       # Main worker loop, dual Ollama routing (14b/3b)
├── billo/                     # Billo Autonomous Orchestrator API
│   ├── __init__.py
│   ├── config.py              # Centralized environment configuration
│   └── app.py                 # FastAPI service: GPU-only, VPS-safe & Hybrid routes
├── tools/                     # Operational & CLI Management
│   └── context2_client.py     # CLI for handovers, queries, and compression
└── deploy/                    # VPS Infrastructure & Automation
    ├── vps-install.sh         # Turnkey Ubuntu 24.04 installer for Hostinger VPS
    ├── systemd/
    │   ├── billo-api.service    # FastAPI systemd service (over Unix socket)
    │   └── billo-worker.service # Background worker systemd service
    ├── nginx/
    │   └── billo.conf         # Nginx reverse proxy configuration
    ├── docker/
    │   ├── docker-compose.yml # Containerized Traefik + API + Worker + Ollama
    │   ├── Dockerfile.api     # Multi-stage API image
    │   └── Dockerfile.worker  # Dedicated Worker image
    └── scripts/
        ├── setup_tunnel.sh    # SSH Tunnel manager (local 11435 -> VPS 11434)
        ├── Start-Billo.ps1    # Safe Windows 11 launcher (avoids reserved $PID)
        └── check_health.sh    # System verification & diagnostic script
```

---

## Hostinger VPS Deployment (Ubuntu 24.04)

Target host: set explicitly with `BILLO_VPS_HOST`.
Domains: `billo.tech`, `arc.billo.tech`

### 1. Run Turnkey Installer
From the root of the extracted package on your VPS:
```bash
sudo bash deploy/vps-install.sh
```

The script performs the following automatically:
1. Installs OS packages (`nginx`, `certbot`, `python3-venv`, `sqlite3`, `ufw`).
2. Creates the non-login system user `billo` and installs code under `/opt/billo`.
3. Installs Ollama and downloads `qwen2.5:3b` for local CPU inference.
4. Configures Python virtual environment and installs dependencies.
5. Deploys systemd units (`billo-api.service` and `billo-worker.service`).
6. Configures Nginx reverse proxy over Unix socket `/run/billo/billo.sock`.
7. Locks down UFW firewall (SSH, HTTP, HTTPS allowed; Ollama port 11434 blocked externally).

### 2. Obtain Free SSL Certificates
```bash
sudo certbot --nginx -d billo.tech -d www.billo.tech -d arc.billo.tech
```

### 3. Verify System Health
```bash
bash deploy/scripts/check_health.sh
```

---

## Local GPU Workstation Quickstart (Windows 11)

Hardware: Intel i7-12700K | NVIDIA RTX 3080 Ti | 32GB DDR5  
Location: `F:\Billo\`

1. **Ensure Ollama is running locally** with `qwen2.5-coder:14b`:
   ```cmd
   ollama run qwen2.5-coder:14b
   ```
2. **Execute the startup script**:
   ```powershell
   .\deploy\scripts\Start-Billo.ps1
   ```
   *Note: Safely terminates any stale Python processes without conflicting with PowerShell's reserved `$PID` variable.*

---

## Docker & Traefik Option

For containerized deployments with automatic SSL certificates:
```bash
cd deploy/docker
docker compose up -d
```

---

## CLI Management Tool (`tools/context2_client.py`)

Test and interact with your deployment directly from the command line:

```bash
# Check API and WAL health
python tools/context2_client.py health

# Retrieve compact LOCI handover (>60% token reduction)
python tools/context2_client.py handover session_production_01

# Query context entity index and review CER efficiency ratio
python tools/context2_client.py query "learning_loop"

# Compress text via VPS Ollama 3b (with heuristic fallback)
python tools/context2_client.py compress /path/to/verbose_log.txt
```
