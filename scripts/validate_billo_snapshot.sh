#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON:-python3}"
cd "$ROOT_DIR"

"$PYTHON_BIN" -m compileall -q loci_engine billo-platform
"$PYTHON_BIN" -m pytest -q
if command -v uv >/dev/null; then
  runtime_lock="$(mktemp)"
  dev_lock="$(mktemp)"
  trap 'rm -f "$runtime_lock" "$dev_lock"' EXIT
  uv pip compile --quiet --universal --python-version 3.11 \
    billo-platform/requirements.txt -o "$runtime_lock"
  uv pip compile --quiet --universal --python-version 3.11 \
    requirements-billo-dev.txt -o "$dev_lock"
  cmp -s <(tail -n +3 "$runtime_lock") \
    <(tail -n +3 billo-platform/requirements.lock)
  cmp -s <(tail -n +3 "$dev_lock") \
    <(tail -n +3 requirements-billo-dev.lock)
fi
(cd billo-platform && sha256sum -c SOURCE-MANIFEST.sha256)
