#!/bin/bash
# install.sh — one-shot installer for the makeshift LOCI stream extractors.
#
# Run once from macOS terminal:
#   bash /Volumes/DevDrive/loci-install/install.sh
#
# What it does:
#   1. Generates HMAC-SHA256 signing key at ~/.config/loci/signing.key (chmod 400)
#   2. Creates /Volumes/DevDrive/Memory-state/ (writable — for audit log + last-seen)
#   3. Temporarily unlocks /Volumes/DevDrive/Memory/
#   4. Moves scripts/ + extractors/ + streams/ into Memory/
#   5. Initializes the hidden loci_facts.db (chmod 400 + chflags uchg)
#   6. Re-locks Memory/ (chflags uchg recursively)
#   7. Runs the first scan across all existing Transcripts/
#
# Everything except loci_writer.py refuses to touch Memory/.
set -euo pipefail

SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"
STATE="/Volumes/DevDrive/Memory-state"
KEY_DIR="${HOME}/.config/loci"
KEY="${KEY_DIR}/signing.key"

echo "[install] 1/7 — generating HMAC signing key at ${KEY}"
mkdir -p "${KEY_DIR}"
chmod 700 "${KEY_DIR}"
if [ ! -s "${KEY}" ]; then
    # 64 random bytes → hex → the HMAC key
    head -c 64 /dev/urandom | xxd -p -c 999 > "${KEY}"
    chmod 400 "${KEY}"
    echo "[install]   generated new key (keep this file; back it up offline)"
else
    echo "[install]   key already exists — reusing"
fi

echo "[install] 2/7 — creating state dir ${STATE}"
mkdir -p "${STATE}"

echo "[install] 3/7 — unlocking ${MEM} temporarily"
sudo chflags -R nouchg "${MEM}" 2>/dev/null || true

echo "[install] 4/7 — installing scripts + extractors + streams + docs into Memory/"
mkdir -p "${MEM}/scripts" "${MEM}/extractors" "${MEM}/streams"
cp -f "${SRC}"/scripts/*.py     "${MEM}/scripts/"
cp -f "${SRC}"/extractors/*.py  "${MEM}/extractors/"
cp -f "${SRC}"/signature.md     "${MEM}/signature.md"
cp -f "${SRC}"/formulas.md      "${MEM}/formulas.md"
touch "${MEM}/streams/isymprev.jsonl"
touch "${MEM}/streams/qsymprev.jsonl"
touch "${MEM}/streams/loci_facts.sql.jsonl"
chmod 755 "${MEM}"/scripts/*.py "${MEM}"/extractors/*.py

echo "[install] 5/7 — initializing hidden loci_facts.db"
python3 "${MEM}/extractors/loci_facts_extractor.py" >/dev/null 2>&1 || true

echo "[install] 6/7 — re-locking Memory/ (chflags uchg)"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo "[install] 7/7 — first-run scan of Transcripts/"
python3 "${MEM}/extractors/session_scanner.py" || true

echo ""
echo "[install] done."
echo "  audit log:    ${STATE}/audit.jsonl"
echo "  facts DB:     /Volumes/DevDrive/.loci-facts.db  (hidden, chmod 400, uchg)"
echo "  signing key:  ${KEY}                            (chmod 400 — back this up)"
echo ""
echo "To re-scan later:  python3 ${MEM}/extractors/session_scanner.py"
echo "To cron every 30m: */30 * * * * /usr/bin/python3 ${MEM}/extractors/session_scanner.py >> ${STATE}/scanner.log 2>&1"
