#!/bin/bash
# patch.sh — apply post-install additions: values.md + Critical Heat formula
#            + updated loci_query.py + seed the two Values into loci_facts.
#
# Safe to re-run. Temp-unlocks Memory, patches, re-locks.
set -euo pipefail

SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"

echo "[patch] installing all docs + updated formulas.md + updated loci_query.py + strategy/arsenal scripts"
cp -f "${SRC}/values.md"          "${MEM}/values.md"
cp -f "${SRC}/critical-heat.md"   "${MEM}/critical-heat.md"
cp -f "${SRC}/focus.md"           "${MEM}/focus.md"
cp -f "${SRC}/arsenal.md"         "${MEM}/arsenal.md"
cp -f "${SRC}/strategies.md"      "${MEM}/strategies.md"
cp -f "${SRC}/ethics-of-learning.md" "${MEM}/ethics-of-learning.md"
cp -f "${SRC}/formulas.md"        "${MEM}/formulas.md"
cp -f "${SRC}/extractors/loci_query.py" "${MEM}/extractors/loci_query.py"
cp -f "${SRC}/scripts/crypto_util.py"          "${MEM}/scripts/crypto_util.py"
cp -f "${SRC}/scripts/set_strategy_password.py" "${MEM}/scripts/set_strategy_password.py"
cp -f "${SRC}/scripts/strategy_writer.py"       "${MEM}/scripts/strategy_writer.py"
cp -f "${SRC}/scripts/strategy_activator.py"    "${MEM}/scripts/strategy_activator.py"
cp -f "${SRC}/scripts/arsenal_writer.py"        "${MEM}/scripts/arsenal_writer.py"
chmod 755 "${MEM}"/scripts/*.py

echo "[patch] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo "[patch] seeding Values V1 + V2 into loci_facts (tier=VALUES)"
python3 "${SRC}/seed_values.py"

echo "[patch] opening FOCUS: get LOCI ∞ up on billo-pc"
python3 "${SRC}/set_focus.py" \
    --entity "LOCI" \
    --key "restart_on_billo_pc" \
    --value "Bring LOCI ∞ back online on Windows workstation (3080 Ti + 5060 Ti) with phi4-14B, cut API spend to near-zero, restore income, neutralize Arc. Family must not starve." \
    --target-days 30 \
    || echo "[patch] focus already open (that's fine; use set_focus.py --show to inspect)"

echo "[patch] ensuring cryptography package is available (needed by strategy tier)"
if ! python3 -c "import cryptography" 2>/dev/null; then
    # try the range of pip install variants that work across environments
    pip3 install cryptography 2>/dev/null \
      || pip3 install --user cryptography 2>/dev/null \
      || pip3 install --break-system-packages cryptography 2>/dev/null \
      || echo "[patch] cryptography install failed — run manually: pip3 install cryptography (or with --user)"
fi

echo ""
echo "[patch] NEXT STEPS (manual, at your discretion):"
echo "  1. Set your strategy password (only if / when you want the STRATEGIES tier):"
echo "       python3 ${MEM}/scripts/set_strategy_password.py"
echo "  2. Write an arsenal item:"
echo "       python3 ${MEM}/scripts/arsenal_writer.py --entity 'gpu.3080ti' \\"
echo "           --key 'phi4-14b-throughput' --value '34 tokens/s fp16, 12GB VRAM'"
echo "  3. Write a strategy (only after step 1):"
echo "       cat <<'END' | python3 ${MEM}/scripts/strategy_writer.py \\"
echo "           --name 'restore_income' --intent-hint 'restart Bybit paper→testnet→live'"
echo "       <your strategy payload>"
echo "       END"
echo ""
echo "[patch] done."
echo "  Verify values:   python3 ${MEM}/extractors/loci_query.py --q 'test' | python3 -c 'import json,sys; d=json.load(sys.stdin); print(\"values:\", d[\"counts\"][\"values\"])'"
echo "  Inspect focus:   python3 ${SRC}/set_focus.py --show"
echo "  Resolve later:   python3 ${SRC}/set_focus.py --resolve fulfilled"
