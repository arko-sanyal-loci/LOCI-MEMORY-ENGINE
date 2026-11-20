#!/usr/bin/env bash
# push_station0.sh — apply the pending patches and push to canonical.
#
# Does NOT contain a token. Export GITHUB_TOKEN in your shell first:
#   export GITHUB_TOKEN="<paste at the prompt, never in a file>"
#   ./push_station0.sh
#
# The token lives only in this shell's environment for this one session —
# it is never written to disk by this script.
set -euo pipefail

if [ -z "${GITHUB_TOKEN:-}" ]; then
    echo "GITHUB_TOKEN is not set. Run:"
    echo "  export GITHUB_TOKEN=\"<your token>\""
    echo "then re-run this script."
    exit 1
fi

cd "$HOME/loci-memory-engine"

echo "=== Applying patches ==="
for p in 0001-Apply-loci-gpu-param_size-naming-convention-across-c.patch \
         0002-Unify-ethics-layer-extract-Learning-Core-add-store.p.patch \
         0003-Add-end-to-end-benchmark-for-unified-ethics-layer.patch; do
    if [ ! -f "$p" ]; then
        echo "Missing $p in $(pwd) — download it from the chat first."
        exit 1
    fi
    git am "$p"
done

echo "=== Pushing with token from environment (never written to disk) ==="
git -c credential.helper= push "https://arko-sanyal-loci:${GITHUB_TOKEN}@github.com/arko-sanyal-loci/LOCI-MEMORY-ENGINE.git" main

echo "=== Done. Unsetting GITHUB_TOKEN from this shell. ==="
unset GITHUB_TOKEN
