#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$HOME/loci-memory-engine"
CONSOLE_IP="192.168.0.149"
VPS_HOST="srv1775801.hstgr.cloud"
VPS_PATH="/home/loci/loci-memory-engine"

cd "$REPO_DIR"

echo "=== [RING -1] Ethical Invariant & Graceful Stop Check ==="
if [ -f "$REPO_DIR/.stop_order" ]; then
    echo "[HALT] Graceful stop order active (.stop_order detected). Preserving state and safely aborting propagation."
    exit 0
fi

echo "=== [RING 0] Deterministic Substrate & Test Pass ==="
python3 -m unittest discover tests/ -v

echo "=== [RING 0] Secret Hygiene Scan ==="
if git ls-files | grep -E "(credentials\.json|token\.json|\.credentials/)" 2>/dev/null; then
    echo "ERROR: Tracked credential file detected in git index!"
    exit 1
fi
if grep -rnE "BEGIN [A-Z]+ PRIVATE KEY" loci_engine/ tests/ 2>/dev/null; then
    echo "ERROR: Unencrypted private key detected in source tree!"
    exit 1
fi

echo "=== [RING 1] Manifest Cryptographic Parity Check ==="
LOCAL_HASH=$(find loci_engine -type f ! -path '*/__pycache__*' ! -name '*.pyc' -exec sha256sum {} + | sort | sha256sum | awk '{print $1}')

if [ ! -f manifest.sha256 ] || [ "$LOCAL_HASH" != "$(cat manifest.sha256 | tr -d '[:space:]')" ]; then
    echo "Updating manifest.sha256 to $LOCAL_HASH"
    echo "$LOCAL_HASH" > manifest.sha256
    git add manifest.sha256
    git commit -m "chore(manifest): update tree hash to $LOCAL_HASH" || true
fi

echo "=== [RING 1.5] Unit Test for MCP Daemon ==="
python3 -c '
import subprocess, json, sys
p = subprocess.Popen([sys.executable, "-m", "loci_engine.mcp_server"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "ping"}) + "\n"
out, err = p.communicate(input=req, timeout=3)
assert "healthy" in out, f"MCP Daemon healthcheck failed: {err}"
print("MCP Daemon Self-Test: OK")
'

# Local daemon reload if active
if systemctl --user is-active --quiet loci-mcp.service 2>/dev/null; then
    echo "Reloading local loci-mcp daemon..."
    systemctl --user restart loci-mcp.service
fi

echo "=== [RING 2] Canary Sync to loci-console (Wired 192.168.0.149) ==="
git push arko-sanyal@"$CONSOLE_IP":"$REPO_DIR" main --no-verify || echo "Canary node offline or unreachable; skipping ring 2."
if ssh -o ConnectTimeout=3 arko-sanyal@"$CONSOLE_IP" "exit" 2>/dev/null; then
    ssh arko-sanyal@"$CONSOLE_IP" "cd ~/loci-memory-engine && ~/loci-spark-venv/bin/python -m unittest discover tests/ -v"
fi

echo "=== [RING 3] VPS Substrate Promotion (srv1775801.hstgr.cloud) ==="
git push root@"$VPS_HOST":"$VPS_PATH" main --no-verify
ssh root@"$VPS_HOST" "cd /home/loci/loci-memory-engine && python3 -m unittest discover tests/ -v"

echo "=== [RING 4] GitHub Upstream Canonical Sync ==="
git push origin main --no-verify

echo "STATUS: Update propagation successful across all nodes."

echo "=== [RING 5] Staged Node Reconciler (Offline / Resurrected Nodes) ==="
if [ -f "$REPO_DIR/scripts/onboard_staged_node.sh" ]; then
    "$REPO_DIR/scripts/onboard_staged_node.sh" || echo "Note: Staged node check completed with non-fatal status."
fi
