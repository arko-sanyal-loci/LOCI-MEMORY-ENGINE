#!/bin/bash
# patch10.sh — ethical-hacker knowledge base + defender_researcher
set -euo pipefail
SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch10] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"
echo "[patch10] installing ethical-hacker.md + defender_researcher.py + defense_curriculum.json"
cp -f "${SRC}/ethical-hacker.md"                    "${MEM}/ethical-hacker.md"
cp -f "${SRC}/scripts/defender_researcher.py"       "${MEM}/scripts/defender_researcher.py"
cp -f "${SRC}/scripts/defense_curriculum.json"      "${MEM}/scripts/defense_curriculum.json"
chmod 755 "${MEM}"/scripts/*.py
echo "[patch10] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch10] Rebaseline integrity so this intentional patch registers:"
sudo python3 "${MEM}/scripts/integrity_baseline.py" --refresh

echo ""
echo "[patch10] Ready. Commands:"
echo "  python3 ${MEM}/scripts/defender_researcher.py --list                  (see the 30 topics)"
echo "  python3 ${MEM}/scripts/defender_researcher.py --topic macos.unified_logs"
echo "  python3 ${MEM}/scripts/defender_researcher.py --category forensics"
echo "  python3 ${MEM}/scripts/defender_researcher.py --all                   (~15 min, ~\$0.40 total)"
echo ""
echo "  After it runs, retrieve any topic via LOCI:"
echo "  python3 ${MEM}/extractors/loci_query.py --q 'how to detect HID injection'"
echo ""
echo "[patch10] done."
