#!/usr/bin/env bash
# finalize_station0.sh — corrects the two files that got the stale
# Vulkan/Ollama-overflow description instead of the confirmed-real
# SYCL + 35B-MoE Arc setup, commits, runs tests, sets up credential
# caching, and pushes.
#
# Contains NO token. Run from ~/loci-memory-engine, with
# gpu_governor.py and unified_port_registry.md downloaded into the
# SAME directory as this script (e.g. both moved from ~/Downloads
# alongside it).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$HOME/loci-memory-engine"

cd "$REPO"

echo "=== Step 1: sanity checks ==="
if [ ! -f "$SCRIPT_DIR/gpu_governor.py" ] || [ ! -f "$SCRIPT_DIR/unified_port_registry.md" ]; then
    echo "Missing gpu_governor.py or unified_port_registry.md next to this script in $SCRIPT_DIR"
    echo "Download both from the chat into the same folder as this script first."
    exit 1
fi

git status --short
echo

echo "=== Step 2: backing up current (stale) versions ==="
STAMP="$(date +%Y%m%d_%H%M%S)"
cp loci_engine/gpu_governor.py "loci_engine/gpu_governor.py.stale-vulkan-${STAMP}.bak"
cp architecture/unified_port_registry.md "architecture/unified_port_registry.md.stale-vulkan-${STAMP}.bak"
echo "Backed up to loci_engine/gpu_governor.py.stale-vulkan-${STAMP}.bak"
echo "         and architecture/unified_port_registry.md.stale-vulkan-${STAMP}.bak"

echo
echo "=== Step 3: dropping in the corrected, SYCL-accurate versions ==="
cp "$SCRIPT_DIR/gpu_governor.py" loci_engine/gpu_governor.py
cp "$SCRIPT_DIR/unified_port_registry.md" architecture/unified_port_registry.md

echo
echo "=== Step 4: verifying import + full test suite ==="
python3 -c "import loci_engine.gpu_governor; print('gpu_governor.py imports OK')"
python3 -m pytest tests/ -q

echo
echo "=== Step 5: committing ==="
git add loci_engine/gpu_governor.py architecture/unified_port_registry.md
git add loci_engine/gpu_governor.py.stale-vulkan-*.bak architecture/unified_port_registry.md.stale-vulkan-*.bak
git commit -m "Fix gpu_governor.py / unified_port_registry.md to match confirmed Arc setup

The version committed earlier tonight described Arc as an Ollama
endpoint running the same 14B model as RTX in an overflow role
(leftover from an earlier, abandoned Vulkan/Ollama attempt). A
station-0 scan confirmed Arc actually runs llama.cpp+SYCL serving
Qwen3.6-35B-A3B-UD-Q4_K_XL.gguf directly on :11435 (systemd
loci-arc.service, active, llama-bench-confirmed 91.2 tok/s) — a
different API entirely, not Ollama. This replaces the stale
description with the naming-convention patch's original version,
which already matched this reality. Stale versions kept alongside
as .bak files for reference, not deleted.

All tests still pass after the swap."

echo
echo "=== Step 6: credential cache (no token stored in any file) ==="
if [ "$(git config --global credential.helper || true)" != "store" ]; then
    git config --global credential.helper store
    echo "credential.helper set to 'store' — next push will prompt once,"
    echo "then cache the token in ~/.git-credentials for future pushes."
else
    echo "credential.helper already set to 'store'."
fi

echo
echo "=== Step 7: push ==="
echo "If prompted, enter your GitHub username and a CURRENT, UN-REVOKED"
echo "token as the password. Never paste it into this terminal as part"
echo "of a URL — type it only at this interactive prompt."
git push origin main

echo
echo "=== Done ==="
