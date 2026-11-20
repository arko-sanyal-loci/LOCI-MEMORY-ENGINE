#!/usr/bin/env bash
# Run this on the workstation — paste the full output back to Claude
set -euo pipefail

echo "========================================"
echo " LOCI WORKSTATION DIAGNOSTIC"
echo " $(date)"
echo "========================================"

echo
echo "=== [1] NETWORK INTERFACES ==="
ip addr show

echo
echo "=== [2] ARP / NEIGHBOUR TABLE ==="
ip neigh show

echo
echo "=== [3] ESTABLISHED CONNECTIONS ==="
ss -tnp state established

echo
echo "=== [4] LOGGED IN USERS ==="
who
echo "---"
w

echo
echo "=== [5] RECENT LOGINS ==="
last -n 20

echo
echo "=== [6] ACTIVE SSH SESSIONS ==="
ps aux | grep -E '[s]shd' | grep -v grep || echo "none"

echo
echo "=== [7] REMOTE DESKTOP / VNC PROCESSES ==="
ps aux | grep -iE '[v]nc|[x]rdp|[t]eamviewer|[a]nydesk|[r]ustdesk|[n]omachine' || echo "none found"

echo
echo "=== [8] LISTENING PORTS ==="
ss -tlnp

echo
echo "=== [9] ACTUAL IPs THIS MACHINE HOLDS ==="
hostname -I

echo
echo "=== [10] UNIT TESTS ==="
cd "$(dirname "${BASH_SOURCE[0]}")/../.." 2>/dev/null \
  || { echo "repository not found — skipping tests"; exit 0; }

if [ -d tests ]; then
    python3 -m pytest -q tests 2>&1
else
    echo "No tests/ directory found in $(pwd)"
fi

echo
echo "========================================"
echo " DIAGNOSTIC COMPLETE — paste above output"
echo "========================================"
