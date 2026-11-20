#!/usr/bin/env bash
# Regenerate manifest.sha256: the content hash of loci_engine/ that node_sync.sh
# and check_remote_parity.sh compare against. Run it after every change to
# loci_engine/ and commit the result; tests/test_manifest.py fails until you do.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"
# shellcheck source=engine_hash.sh
source scripts/ops/engine_hash.sh
engine_hash > manifest.sha256
echo "manifest.sha256 = $(cat manifest.sha256)"
