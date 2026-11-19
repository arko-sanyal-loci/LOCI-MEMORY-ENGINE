#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/_nodes.sh"
require_nodes_var VPS_HOST VPS_USER VPS_PATH
HOST="${VPS_USER}@${VPS_HOST}"
cd "$LOCI_REPO_DIR"
REMOTE_DIR="$VPS_PATH"

echo "Syncing loci-memory-engine workspace to $HOST..."
tar -czf - --exclude='.git' -C "$(pwd)" . | ssh "$HOST" "
  mkdir -p $REMOTE_DIR && \
  tar -xzf - -C $REMOTE_DIR && \
  chown -R loci:loci $REMOTE_DIR
"

echo "Running parity check..."
"$(dirname "${BASH_SOURCE[0]}")/check_remote_parity.sh"

echo "Triggering evaluation service..."
ssh "$HOST" "su - loci -c '
  export XDG_RUNTIME_DIR=/run/user/\$(id -u)
  export DBUS_SESSION_BUS_ADDRESS=unix:path=\$XDG_RUNTIME_DIR/bus
  systemctl --user restart loci-engine.service
  systemctl --user status loci-engine.service --no-pager
'"
