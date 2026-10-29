#!/usr/bin/env bash
set -euo pipefail

HOST="root@srv1775801.hstgr.cloud"
REMOTE_DIR="/home/loci/loci-memory-engine"

echo "Syncing loci-memory-engine workspace to $HOST..."
tar -czf - --exclude='.git' -C "$(pwd)" . | ssh "$HOST" "
  mkdir -p $REMOTE_DIR && \
  tar -xzf - -C $REMOTE_DIR && \
  chown -R loci:loci $REMOTE_DIR
"

echo "Running parity check..."
./check_remote_parity.sh

echo "Triggering evaluation service..."
ssh "$HOST" "su - loci -c '
  export XDG_RUNTIME_DIR=/run/user/\$(id -u)
  export DBUS_SESSION_BUS_ADDRESS=unix:path=\$XDG_RUNTIME_DIR/bus
  systemctl --user restart loci-engine.service
  systemctl --user status loci-engine.service --no-pager
'"
