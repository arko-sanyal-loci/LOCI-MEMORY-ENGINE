#!/usr/bin/env bash
set -euo pipefail

# Runs on a mirror node (e.g. the VPS) to restore parity with origin/main.
# WARNING: runs `git reset --hard` and `git clean -fd` on drift. Never run it
# on a checkout you edit.
source "$(dirname "${BASH_SOURCE[0]}")/_nodes.sh"
WORKSPACE="${LOCI_SYNC_WORKSPACE:-$LOCI_REPO_DIR}"
cd "$WORKSPACE"

# 1. Fetch remote tracking refs securely via SSH deploy key
git fetch origin main --quiet

# 2. Extract upstream manifest hash
REMOTE_HASH=$(git show origin/main:manifest.sha256 2>/dev/null | tr -d '[:space:]' || true)

# 3. Calculate local engine tree hash (same definition as update_manifest.sh;
#    bytecode caches excluded, or every node looks diverged forever)
# shellcheck source=engine_hash.sh
source "$(dirname "${BASH_SOURCE[0]}")/engine_hash.sh"
LOCAL_HASH=$(engine_hash)

# 4. Check for divergence or local working tree contamination
DIRTY_COUNT=$(git status --porcelain | wc -l)

if [ "$LOCAL_HASH" != "$REMOTE_HASH" ] || [ "$DIRTY_COUNT" -ne 0 ]; then
  echo "Invariant violated (Local: $LOCAL_HASH, Remote: $REMOTE_HASH, Dirty: $DIRTY_COUNT). Restoring parity..."
  # Never destroy local work silently: stash tracked AND untracked changes
  # first (recover with `git stash list` / `git stash pop`). Before
  # 2026-11-19 this ran reset --hard + clean -fd with no backup.
  if [ "$DIRTY_COUNT" -ne 0 ]; then
    git stash push --include-untracked -m "node_sync backup $(date -u +%Y%m%dT%H%M%SZ)" >/dev/null
    echo "Local changes stashed before reset."
  fi
  git reset --hard origin/main
  
  if [ -f "/run/user/$(id -u)/bus" ]; then
    export XDG_RUNTIME_DIR=/run/user/$(id -u)
    export DBUS_SESSION_BUS_ADDRESS=unix:path=$XDG_RUNTIME_DIR/bus
    systemctl --user restart loci-engine.service || true
  fi
  echo "Substrate parity restored to $(git rev-parse --short HEAD)"
fi
