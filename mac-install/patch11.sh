#!/bin/bash
# patch11.sh — install gigabyte_scan.py (LOCI/formulas/docs harvester)
set -euo pipefail
SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch11] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"
echo "[patch11] installing gigabyte_scan.py"
cp -f "${SRC}/scripts/gigabyte_scan.py" "${MEM}/scripts/gigabyte_scan.py"
chmod 755 "${MEM}/scripts/gigabyte_scan.py"
echo "[patch11] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch11] Rebaseline integrity so this intentional patch registers:"
sudo python3 "${MEM}/scripts/integrity_baseline.py" --refresh

echo ""
echo "[patch11] Ready. Next steps (once Gigabyte 2TB is mounted):"
echo "  # 1. Dry-run (list what would be ingested, write nothing)"
echo "  python3 ${MEM}/scripts/gigabyte_scan.py --root '/Volumes/Gigabyte 2TB' --dry-run --limit 200"
echo ""
echo "  # 2. Full ingest into loci_facts (tier=ARSENAL)"
echo "  python3 ${MEM}/scripts/gigabyte_scan.py --root '/Volumes/Gigabyte 2TB'"
echo ""
echo "  # 3. Retrieve after"
echo "  python3 ${MEM}/extractors/loci_query.py --q 'heat map formula' --k 10"
echo ""
echo "[patch11] done."
