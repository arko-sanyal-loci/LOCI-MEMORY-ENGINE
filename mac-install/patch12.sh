#!/bin/bash
# patch12.sh — sigword bootstrap fix + OPTIMIZE_SOURCE_OF_TRUTH.md preservation
# + transcript_ingest.py
#
# Fixes:
#   - New sessions were treating sigword `roz@` as a truncated email address.
#     Bootstrap sigword block was too vague. Rewritten with SHAPE, ACTION,
#     ANTI-PATTERN, and verify command.
#   - sigword_utils.py had no CLI; new sessions couldn't verify tokens.
#     Added --check-stdin / --scrub-stdin / --verify-token.
#   - OPTIMIZE_SOURCE_OF_TRUTH.md (Billo tier-routing standard, 405 lines)
#     was orphaned in t7-carve. Preserved into Memory/references/.
#   - transcript_ingest.py added for per-session Memory summaries.
set -euo pipefail
SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch12] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"

echo "[patch12] installing updated session_bootstrap.py (strong sigword block)"
cp -f "${SRC}/scripts/session_bootstrap.py"   "${MEM}/scripts/session_bootstrap.py"

echo "[patch12] installing updated sigword_utils.py (with CLI)"
cp -f "${SRC}/scripts/sigword_utils.py"       "${MEM}/scripts/sigword_utils.py"

echo "[patch12] installing transcript_ingest.py"
cp -f "${SRC}/scripts/transcript_ingest.py"   "${MEM}/scripts/transcript_ingest.py"

echo "[patch12] preserving OPTIMIZE_SOURCE_OF_TRUTH.md into Memory/references/"
mkdir -p "${MEM}/references"
cp -f "${SRC}/references/OPTIMIZE_SOURCE_OF_TRUTH.md" \
      "${MEM}/references/OPTIMIZE_SOURCE_OF_TRUTH.md"

chmod 755 "${MEM}"/scripts/*.py

echo "[patch12] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch12] regenerating ~/.claude/CLAUDE.md so the fix is live NOW:"
python3 "${MEM}/scripts/session_bootstrap.py"

echo ""
echo "[patch12] rebaseline integrity so this intentional patch registers:"
sudo python3 "${MEM}/scripts/integrity_baseline.py" --refresh

echo ""
echo "[patch12] === VERIFICATION ==="
echo ""
echo "[patch12] a) sigword CLI works?"
if python3 "${MEM}/scripts/sigword_utils.py" --verify-token 'not-the-real-sigword@' >/dev/null 2>&1; then
  echo "  FAIL: verify-token said match for garbage input"; exit 1
else
  echo "  OK: verify-token exit=1 for garbage input"
fi
echo ""
echo "[patch12] b) new CLAUDE.md has the strong sigword block?"
if grep -q "authentication marker" ~/.claude/CLAUDE.md; then
  echo "  OK: sigword block installed"
else
  echo "  FAIL: sigword block missing"; exit 1
fi
echo ""
echo "[patch12] c) OPTIMIZE_SOURCE_OF_TRUTH.md preserved?"
wc -l "${MEM}/references/OPTIMIZE_SOURCE_OF_TRUTH.md"
echo ""
echo "[patch12] === NEXT STEPS ==="
echo ""
echo "1. Test sigword in a NEW Claude Code session — type your sigword. It should:"
echo "   - NOT ask 'did you mean roza@…'"
echo "   - NOT echo it back"
echo "   - Silently proceed with rest of your message"
echo ""
echo "2. Run transcript ingest (dry-run first):"
echo "   python3 ${MEM}/scripts/transcript_ingest.py --dry-run"
echo "   python3 ${MEM}/scripts/transcript_ingest.py --only-new"
echo ""
echo "3. Add OPTIMIZE_SOURCE_OF_TRUTH.md as an arsenal fact for retrieval:"
echo "   sudo python3 ${MEM}/scripts/arsenal_writer.py \\"
echo "     --entity reference.billo --key optimize_source_of_truth \\"
echo "     --value \"\$(cat ${MEM}/references/OPTIMIZE_SOURCE_OF_TRUTH.md)\" \\"
echo "     --source recovered_from_t7_carve"
echo ""
echo "[patch12] done."
