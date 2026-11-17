#!/bin/bash
# patch6.sh — install Honor layer + V5.
set -euo pipefail
SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch6] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"

echo "[patch6] installing honor + deception scanner + updated loci_writer"
cp -f "${SRC}/honor.md"                       "${MEM}/honor.md"
cp -f "${SRC}/scripts/honor_check.py"         "${MEM}/scripts/honor_check.py"
cp -f "${SRC}/scripts/deception_scan.py"      "${MEM}/scripts/deception_scan.py"
cp -f "${SRC}/scripts/loci_writer.py"         "${MEM}/scripts/loci_writer.py"
chmod 755 "${MEM}"/scripts/*.py

echo "[patch6] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch6] Seed V5 (Honor) into VALUES — needs sudo:"
sudo python3 "${MEM}/scripts/values_admin.py" --add \
    --entity "value.honor" \
    --key    "V5" \
    --value  "Honor: faithfulness × truth × cost_borne × transparency × repair_capacity, conjunctive. Reciprocity multiplier for protected_class. See honor.md. What Arc did to Roza — extractive access without reciprocity — is refused by construction." \
    || echo "[patch6] V5 seed skipped (may already exist or need retry)"

echo ""
echo "[patch6] Scan whole Memory/ for deception patterns:"
python3 "${MEM}/scripts/deception_scan.py" --target "${MEM}"
echo "[patch6] done."
