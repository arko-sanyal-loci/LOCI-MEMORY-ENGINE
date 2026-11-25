#!/usr/bin/env bash
# ==============================================================================
# setup_tunnel.sh - Persistent SSH Tunnel from Local Workstation to Hostinger VPS
# Maps local port 11435 -> VPS localhost:11434 (qwen2.5:3b)
# ==============================================================================

VPS_IP="${1:-${BILLO_VPS_HOST:-}}"
VPS_USER="${2:-root}"
LOCAL_PORT="11435"
REMOTE_PORT="11434"

if [[ -z "$VPS_IP" ]]; then
    echo "Set BILLO_VPS_HOST or pass the VPS hostname as the first argument." >&2
    exit 2
fi

echo "Setting up SSH tunnel: 127.0.0.1:${LOCAL_PORT} -> ${VPS_USER}@${VPS_IP}:${REMOTE_PORT}..."

while true; do
    ssh -N \
        -o ServerAliveInterval=30 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -L "127.0.0.1:${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT}" \
        "${VPS_USER}@${VPS_IP}" || true
    echo "Tunnel interrupted. Reconnecting in 5 seconds..."
    sleep 5
done
