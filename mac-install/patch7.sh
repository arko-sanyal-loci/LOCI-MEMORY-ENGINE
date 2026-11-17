#!/bin/bash
# patch7.sh — integrity monitor + injection defense
set -euo pipefail
SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch7] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"
echo "[patch7] installing integrity scripts + updated loci_writer (quarantine-aware)"
cp -f "${SRC}/scripts/integrity_baseline.py"  "${MEM}/scripts/integrity_baseline.py"
cp -f "${SRC}/scripts/integrity_monitor.py"   "${MEM}/scripts/integrity_monitor.py"
cp -f "${SRC}/scripts/loci_writer.py"         "${MEM}/scripts/loci_writer.py"
chmod 755 "${MEM}"/scripts/*.py
echo "[patch7] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch7] baselining Memory/ (first snapshot for drift-detection)..."
sudo python3 "${MEM}/scripts/integrity_baseline.py" --refresh

echo ""
echo "[patch7] verify (should say 'clean'):"
python3 "${MEM}/scripts/integrity_monitor.py" --check && echo "clean" || echo "drift or injection"

echo ""
echo "[patch7] To run continuous drift-detection (recommended — background it):"
echo "         nohup python3 ${MEM}/scripts/integrity_monitor.py --watch --interval 30 > /Volumes/DevDrive/Memory-state/integrity/watch.log 2>&1 &"
echo "         # or launchd it — see /Volumes/DevDrive/Memory/scripts/integrity_monitor.py --help"
