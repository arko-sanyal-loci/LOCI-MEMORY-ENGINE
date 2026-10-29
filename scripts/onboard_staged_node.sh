#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$HOME/loci-memory-engine"
CONFIG_FILE="$REPO_DIR/config/nodes.env"

if [ -f "$CONFIG_FILE" ]; then
    source "$CONFIG_FILE"
else
    echo "ERROR: Missing $CONFIG_FILE"
    exit 1
fi

TARGET_IP="${1:-$MAC_MINI_IP}"
TARGET_USER="${2:-$MAC_MINI_USER}"
TARGET_PATH="${3:-$MAC_MINI_PATH}"

echo "=== Probing Staged Node: $TARGET_USER@$TARGET_IP ==="

# 1. Non-blocking ICMP ping (1 packet, 1s timeout)
if ! ping -c 1 -W 1 "$TARGET_IP" > /dev/null 2>&1; then
    echo "STATUS: Node $TARGET_IP is OFFLINE / UNREACHABLE."
    echo "Staged isolation maintained. Zero drift introduced."
    exit 0
fi

# 2. Port 22 SSH probe (2s timeout)
if ! nc -z -w 2 "$TARGET_IP" 22 > /dev/null 2>&1; then
    echo "STATUS: Node $TARGET_IP pingable, but SSH (port 22) is not listening."
    echo "Awaiting Remote Login configuration post-DFU."
    exit 0
fi

echo "Node $TARGET_IP is ONLINE with port 22 open. Initiating staged verification..."

# 3. Darwin / Apple Silicon sanity check
REMOTE_SYS_INFO=$(ssh -o ConnectTimeout=3 "$TARGET_USER@$TARGET_IP" "uname -sm" 2>/dev/null || true)
if [ -z "$REMOTE_SYS_INFO" ]; then
    echo "WARNING: SSH connection handshake failed. Host key or authorized_keys check needed."
    exit 0
fi
echo "Target Platform Confirmed: $REMOTE_SYS_INFO"

# 4. Push substrate to target
echo "Syncing repository substrate to target..."
ssh "$TARGET_USER@$TARGET_IP" "mkdir -p $(dirname "$TARGET_PATH")"
git push "$TARGET_USER@$TARGET_IP:$TARGET_PATH" main --no-verify

# 5. Remote Substrate Verification Gate
echo "Executing substrate integrity check on target..."
LOCAL_MANIFEST=$(cat "$REPO_DIR/manifest.sha256" | tr -d '[:space:]')

ssh "$TARGET_USER@$TARGET_IP" "bash -s" << REMOTE_VALIDATION
set -euo pipefail
cd "$TARGET_PATH"

# macOS compatible SHA-256 calculation (handles BSD shasum vs coreutils sha256sum)
if command -v sha256sum >/dev/null 2>&1; then
    REMOTE_HASH=\$(find loci_engine -type f -exec sha256sum {} + | sort | sha256sum | awk '{print \$1}')
else
    REMOTE_HASH=\$(find loci_engine -type f | sort | while read -r f; do shasum -a 256 "\$f"; done | shasum -a 256 | awk '{print \$1}')
fi

echo "Remote Substrate SHA: \$REMOTE_HASH"
if [ "\$REMOTE_HASH" != "$LOCAL_MANIFEST" ]; then
    echo "CRITICAL: Substrate mismatch on onboarded node!"
    exit 2
fi

echo "Running native Python unit tests..."
python3 -m unittest discover tests/ -v
REMOTE_VALIDATION

echo "=========================================================="
echo "STAGED ONBOARDING SUCCESSFUL: $TARGET_IP verified in parity."
echo "=========================================================="
