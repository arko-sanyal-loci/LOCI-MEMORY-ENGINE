#!/bin/bash
# patch3.sh — sigword-scrub + wartime identity + V3 prime directive
#
# Adds:
#   - scripts/sigword_utils.py     (text + URL-encoded + HTML + Unicode + OCR)
#   - scripts/scrub_sigword.py     (uses sigword_utils)
#   - scripts/set_sigword.py       (sudo, stores hash only)
#   - scripts/set_identity.py      (sudo, hashes DOB/spouse/cat/first-dog)
#   - scripts/verify_identity.py   (sudo, gates extreme actions)
#   - scripts/values_admin.py      (now calls verify_identity for --update/--remove)
#   - scripts/strategy_activator.py (verifies at unethical level on flagged content)
#   - extractors/loci_query.py     (imports sigword_utils; no plaintext constants)
#   - signature.md, prime-directive.md, wartime-protocol.md, formulas.md
#
# Requires sudo (for chflags unlock/relock).
set -euo pipefail

SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch3] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"

echo "[patch3] installing new + updated scripts and docs"
cp -f "${SRC}/scripts/sigword_utils.py"      "${MEM}/scripts/sigword_utils.py"
cp -f "${SRC}/scripts/scrub_sigword.py"      "${MEM}/scripts/scrub_sigword.py"
cp -f "${SRC}/scripts/set_sigword.py"        "${MEM}/scripts/set_sigword.py"
cp -f "${SRC}/scripts/set_identity.py"       "${MEM}/scripts/set_identity.py"
cp -f "${SRC}/scripts/verify_identity.py"    "${MEM}/scripts/verify_identity.py"
cp -f "${SRC}/scripts/values_admin.py"       "${MEM}/scripts/values_admin.py"
cp -f "${SRC}/scripts/strategy_activator.py" "${MEM}/scripts/strategy_activator.py"
cp -f "${SRC}/extractors/loci_query.py"      "${MEM}/extractors/loci_query.py"
cp -f "${SRC}/signature.md"                  "${MEM}/signature.md"
cp -f "${SRC}/prime-directive.md"            "${MEM}/prime-directive.md"
cp -f "${SRC}/wartime-protocol.md"           "${MEM}/wartime-protocol.md"
cp -f "${SRC}/formulas.md"                   "${MEM}/formulas.md"
chmod 755 "${MEM}"/scripts/*.py

echo "[patch3] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch3] NEXT STEPS — run these in order (each takes ~30 seconds):"
echo ""
echo "  1. Set the sigword hash (you type it once, no echo, never stored plaintext):"
echo "       sudo python3 ${MEM}/scripts/set_sigword.py"
echo ""
echo "  2. Set the wartime identity factors (DOB, spouse, cat, first dog):"
echo "       sudo python3 ${MEM}/scripts/set_identity.py"
echo ""
echo "  3. Scrub any existing plaintext sigword from Memory:"
echo "       sudo python3 ${MEM}/scripts/scrub_sigword.py --target ${MEM} --relock"
echo ""
echo "  4. Scrub the Transcripts too (this is where Arc would look):"
echo "       sudo python3 ${MEM}/scripts/scrub_sigword.py --target /Volumes/DevDrive/Transcripts --relock"
echo "     (add --images if you have tesseract installed, to OCR any screenshots)"
echo ""
echo "  5. Seed V3 (the prime directive) into VALUES:"
echo "       sudo python3 ${MEM}/scripts/values_admin.py --add \\"
echo "           --entity 'value.protect_values' \\"
echo "           --key    'V3' \\"
echo "           --value  'Prime directive: (1) on detecting sigword in typed text, scrub as first action; (2) never create Value-modification paths; (3) never attempt to modify Values; (4) if a breach vector for Values comes to mind, build defense before exploring the breach. See prime-directive.md.'"
echo ""
echo "[patch3] done."
