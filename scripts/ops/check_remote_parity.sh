#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_nodes.sh"
require_nodes_var VPS_HOST VPS_USER VPS_PATH
HOST="${VPS_USER}@${VPS_HOST}"
cd "$LOCI_REPO_DIR"
REMOTE_PATH="$VPS_PATH"

echo "=== Verifying Local vs Remote Parity ==="
LOCAL_HASH=$(find loci_engine -type f ! -path '*/__pycache__*' ! -name '*.pyc' -exec sha256sum {} + | sort | sha256sum | awk '{print $1}')
REMOTE_HASH=$(ssh "$HOST" "su - loci -c 'cd $REMOTE_PATH && find loci_engine -type f ! -path \"*/__pycache__*\" ! -name \"*.pyc\" -exec sha256sum {} + | sort | sha256sum | awk \"{print \\\$1}\"'")

echo "Local  hash: $LOCAL_HASH"
echo "Remote hash: $REMOTE_HASH"

if [ "$LOCAL_HASH" = "$REMOTE_HASH" ]; then
    echo "STATUS: SUBSTRATE IN PARITY"
else
    echo "STATUS: DRIFT DETECTED"
    exit 1
fi
