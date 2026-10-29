#!/usr/bin/env bash
set -euo pipefail

HOST="root@srv1775801.hstgr.cloud"
REMOTE_PATH="/home/loci/loci-memory-engine"

echo "=== Verifying Local vs Remote Parity ==="
LOCAL_HASH=$(find loci_engine -type f -exec sha256sum {} + | sort | sha256sum | awk '{print $1}')
REMOTE_HASH=$(ssh "$HOST" "su - loci -c 'cd $REMOTE_PATH && find loci_engine -type f -exec sha256sum {} + | sort | sha256sum | awk \"{print \\\$1}\"'")

echo "Local  hash: $LOCAL_HASH"
echo "Remote hash: $REMOTE_HASH"

if [ "$LOCAL_HASH" = "$REMOTE_HASH" ]; then
    echo "STATUS: SUBSTRATE IN PARITY"
else
    echo "STATUS: DRIFT DETECTED"
    exit 1
fi
