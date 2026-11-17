#!/bin/bash
# patch9.sh — dream_worker (the 4th subsystem)
set -euo pipefail
SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch9] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"
echo "[patch9] installing dreaming.md + dream_worker.py"
cp -f "${SRC}/dreaming.md"                    "${MEM}/dreaming.md"
cp -f "${SRC}/scripts/dream_worker.py"        "${MEM}/scripts/dream_worker.py"
chmod 755 "${MEM}"/scripts/*.py
echo "[patch9] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch9] Rebaseline integrity so this intentional patch registers:"
sudo python3 "${MEM}/scripts/integrity_baseline.py" --refresh

echo ""
echo "[patch9] Try a dream cycle now:"
echo "         python3 ${MEM}/scripts/dream_worker.py --cycles 100"
echo "         python3 ${MEM}/scripts/dream_worker.py --show 10"
echo ""
echo "[patch9] Schedule nightly dreaming at 3am (recommended):"
echo "         (crontab -l 2>/dev/null; echo '0 3 * * * /usr/bin/python3 ${MEM}/scripts/dream_worker.py --cycles 200 > /Volumes/DevDrive/Memory-state/dream.log 2>&1') | crontab -"
echo ""
echo "[patch9] done."
