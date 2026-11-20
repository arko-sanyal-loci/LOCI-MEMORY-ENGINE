#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_nodes.sh"
require_nodes_var VPS_HOST VPS_USER VPS_PATH
HOST="${VPS_USER}@${VPS_HOST}"
cd "$LOCI_REPO_DIR"
REMOTE_PATH="$VPS_PATH"

echo "=== Verifying Local vs Remote Parity ==="
# shellcheck source=engine_hash.sh
source "$(dirname "${BASH_SOURCE[0]}")/engine_hash.sh"
LOCAL_HASH=$(engine_hash)
REMOTE_HASH=$(ssh "$HOST" "su - loci -c 'cd $REMOTE_PATH && LC_ALL=C find loci_engine -type f ! -path \"*/__pycache__*\" ! -name \"*.pyc\" -exec sha256sum {} + | LC_ALL=C sort | sha256sum | awk \"{print \\\$1}\"'")

echo "Local  hash: $LOCAL_HASH"
echo "Remote hash: $REMOTE_HASH"

if [ "$LOCAL_HASH" = "$REMOTE_HASH" ]; then
    echo "STATUS: SUBSTRATE IN PARITY"
else
    echo "STATUS: DRIFT DETECTED"
    exit 1
fi
