#!/usr/bin/env bash
# ==============================================================================
# deploy/vps-install.sh
# Automated Installation Script for Ubuntu 24.04 LTS (Hostinger VPS)
# Target Host: explicitly selected Hostinger VPS
# Primary Domains: billo.tech, arc.billo.tech
# ==============================================================================
set -euo pipefail

APP_USER="billo"
APP_GROUP="billo"
APP_DIR="/opt/billo"
LOG_DIR="/var/log/billo"
RUN_DIR="/run/billo"
VENV_DIR="${APP_DIR}/venv"
DOMAIN="${BILLO_DOMAIN:-billo.tech}"
ARC_DOMAIN="${ARC_DOMAIN:-arc.billo.tech}"

if [ "$(id -u)" != "0" ]; then
    echo "ERROR: This installation script must be run as root from the Hostinger web console or SSH." >&2
    exit 1
fi

echo "=========================================================================="
echo " Starting Billo & LOCI Unified VPS Installation"
echo " Host: $(hostname -f 2>/dev/null || echo 'VPS') | Date: $(date -u)"
echo "=========================================================================="

echo ">>> [1/7] Updating Base OS & Installing Prerequisites..."
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential curl wget git ufw nginx certbot \
    python3-certbot-nginx python3-pip python3-venv python3-dev \
    sqlite3 libsqlite3-dev ca-certificates rsync htop

echo ">>> [2/7] Creating System User & Directory Layouts..."
if ! id "${APP_USER}" &>/dev/null; then
    useradd --system --shell /usr/sbin/nologin --home-dir "${APP_DIR}" "${APP_USER}"
    echo "Created system user '${APP_USER}'."
fi

mkdir -p "${APP_DIR}/data" "${APP_DIR}/loci" "${APP_DIR}/Workers" "${APP_DIR}/billo" "${APP_DIR}/tools" "${LOG_DIR}" "${RUN_DIR}"
chown -R "${APP_USER}:${APP_GROUP}" "${APP_DIR}" "${LOG_DIR}" "${RUN_DIR}"
chmod 755 "${RUN_DIR}"

echo ">>> [3/7] Installing & Configuring Ollama (VPS CPU Inference)..."
if ! command -v ollama &>/dev/null; then
    echo "Installing Ollama CLI and daemon..."
    curl -fsSL https://ollama.com/install.sh | sh
fi

systemctl daemon-reload
systemctl enable --now ollama
sleep 3

echo "Pulling qwen2.5:3b lightweight model for VPS compression & routing..."
ollama pull qwen2.5:3b || echo "WARNING: Could not pull qwen2.5:3b right now; pull manually later."

echo ">>> [4/7] Setting up Python Virtual Environment..."
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
fi

"${VENV_DIR}/bin/pip" install --upgrade pip setuptools wheel
if [ -f "${APP_DIR}/requirements.txt" ]; then
    "${VENV_DIR}/bin/pip" install -r "${APP_DIR}/requirements.txt"
else
    "${VENV_DIR}/bin/pip" install fastapi "uvicorn[standard]" httpx pydantic sqlite3-api gunicorn
fi

echo ">>> [5/7] Deploying Systemd Services..."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ -f "${SCRIPT_DIR}/systemd/billo-api.service" ]; then
    cp "${SCRIPT_DIR}/systemd/billo-api.service" /etc/systemd/system/billo-api.service
else
    cat << 'SERVICE_API' > /etc/systemd/system/billo-api.service
[Unit]
Description=Billo FastAPI Backend Daemon (over Unix Socket)
After=network.target

[Service]
Type=simple
User=billo
Group=billo
WorkingDirectory=/opt/billo
RuntimeDirectory=billo
RuntimeDirectoryMode=0755
Environment=BILLO_DB_PATH=/opt/billo/data/context2.db
Environment=OLLAMA_VPS_DIRECT=http://127.0.0.1:11434
Environment=TIMEOUT_VPS_COMPRESS=60.0
ExecStart=/opt/billo/venv/bin/uvicorn billo.app:app --uds /run/billo/billo.sock --workers 2 --proxy-headers
Restart=always
RestartSec=5
StandardOutput=append:/var/log/billo/api.log
StandardError=append:/var/log/billo/api_error.log

[Install]
WantedBy=multi-user.target
SERVICE_API
fi

if [ -f "${SCRIPT_DIR}/systemd/billo-worker.service" ]; then
    cp "${SCRIPT_DIR}/systemd/billo-worker.service" /etc/systemd/system/billo-worker.service
else
    cat << 'SERVICE_WORKER' > /etc/systemd/system/billo-worker.service
[Unit]
Description=Billo Learning Loop Background Worker
After=network.target billo-api.service

[Service]
Type=simple
User=billo
Group=billo
WorkingDirectory=/opt/billo
Environment=BILLO_DB_PATH=/opt/billo/data/context2.db
Environment=OLLAMA_VPS_DIRECT=http://127.0.0.1:11434
Environment=TIMEOUT_VPS_COMPRESS=60.0
ExecStart=/opt/billo/venv/bin/python3 Workers/learning_loop.py
Restart=always
RestartSec=5
StandardOutput=append:/var/log/billo/worker.log
StandardError=append:/var/log/billo/worker_error.log

[Install]
WantedBy=multi-user.target
SERVICE_WORKER
fi

systemctl daemon-reload
systemctl enable billo-api.service billo-worker.service

echo ">>> [6/7] Configuring Nginx Reverse Proxy..."
if [ -f "${SCRIPT_DIR}/nginx/billo.conf" ]; then
    cp "${SCRIPT_DIR}/nginx/billo.conf" /etc/nginx/sites-available/billo.conf
fi
ln -sf /etc/nginx/sites-available/billo.conf /etc/nginx/sites-enabled/billo.conf
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl reload nginx

echo ">>> [7/7] Configuring UFW Firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'
# Explicitly block external access to Ollama port 11434 (internal only)
ufw deny 11434/tcp comment 'Block Ollama External'
ufw --force enable

echo "=========================================================================="
echo " Installation Complete!"
echo " Services enabled:"
echo "   - billo-api.service"
echo "   - billo-worker.service"
echo "   - ollama.service"
echo "   - nginx.service"
echo ""
echo " To obtain SSL Certificates via Certbot, run:"
echo "   certbot --nginx -d ${DOMAIN} -d ${ARC_DOMAIN}"
echo "=========================================================================="
