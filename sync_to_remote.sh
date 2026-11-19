#!/usr/bin/env bash
set -euo pipefail

printf 'Remote workspace overlays are disabled. Audit deployment hooks and verify a clean node with node_sync.sh --check.\n' >&2
exit 1
