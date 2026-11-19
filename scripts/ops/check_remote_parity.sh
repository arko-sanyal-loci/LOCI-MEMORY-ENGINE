#!/usr/bin/env bash
set -euo pipefail

HOST="root@srv1775801.hstgr.cloud"
REMOTE_PATH="/home/loci/loci-memory-engine"

echo "=== Verifying Local vs Remote Parity ==="
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/../.."
# shellcheck source=engine_hash.sh
source "$SCRIPT_DIR/engine_hash.sh"
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
