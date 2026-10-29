#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="/home/loci/loci-memory-engine"
STATE_DIR="/home/loci/loci-data"
UPSTREAM_URL="https://raw.githubusercontent.com/arko-sanyal2/loci-memory-engine/main"

export XDG_RUNTIME_DIR=/run/user/$(id -u)
export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus

# 1. Fetch remote manifest / tree hash
REMOTE_MANIFEST=$(curl -sSfL "${UPSTREAM_URL}/manifest.sha256" 2>/dev/null || true)
if [ -z "$REMOTE_MANIFEST" ]; then
  exit 0
fi

# 2. Compare against local state hash
LOCAL_HASH=$(cd "$WORKSPACE" && find loci_engine -type f -exec sha256sum {} + | sort | sha256sum | awk '{print $1}')
REMOTE_HASH=$(echo "$REMOTE_MANIFEST" | sha256sum | awk '{print $1}')

if [ "$LOCAL_HASH" != "$REMOTE_HASH" ]; then
  echo "State divergence detected. Triggering verification..."
  systemctl --user restart loci-engine.service
fi
