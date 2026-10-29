#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="/home/loci/loci-memory-engine"
cd "$WORKSPACE"

# 1. Fetch remote tracking refs securely via SSH deploy key
git fetch origin main --quiet

# 2. Extract upstream manifest hash
REMOTE_HASH=$(git show origin/main:manifest.sha256 2>/dev/null | tr -d '[:space:]' || true)

# 3. Calculate local engine tree hash
LOCAL_HASH=$(find loci_engine -type f -exec sha256sum {} + | sort | sha256sum | awk '{print $1}')

# 4. Check for divergence or local working tree contamination
DIRTY_COUNT=$(git status --porcelain | wc -l)

if [ "$LOCAL_HASH" != "$REMOTE_HASH" ] || [ "$DIRTY_COUNT" -ne 0 ]; then
  echo "Invariant violated (Local: $LOCAL_HASH, Remote: $REMOTE_HASH, Dirty: $DIRTY_COUNT). Restoring parity..."
  git reset --hard origin/main
  git clean -fd
  
  if [ -f "/run/user/$(id -u)/bus" ]; then
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
    systemctl --user restart loci-engine.service || true
  fi
  echo "Substrate parity restored to $(git rev-parse --short HEAD)"
fi
