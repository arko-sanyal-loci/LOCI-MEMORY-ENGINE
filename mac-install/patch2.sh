#!/bin/bash
# patch2.sh — Values immutability layer:
#   - Force heat=1.0 on existing VALUES rows (was 1e9)
#   - Install SQLite triggers that block INSERT/UPDATE/DELETE on tier='VALUES'
#   - Update loci_writer.py to refuse tier='VALUES' patches
#   - Update loci_query.py to force VALUES heat=1.0 on output
#   - Install values_admin.py (sudo-only path for future V3, V4, ...)
#
# Safe to re-run. Idempotent (triggers get DROP+CREATE'd).
set -euo pipefail

SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch2] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"

echo "[patch2] copying updated loci_writer.py + loci_query.py + values_admin.py + migrate_values_lock.py + seed_values.py"
cp -f "${SRC}/scripts/loci_writer.py"           "${MEM}/scripts/loci_writer.py"
cp -f "${SRC}/scripts/values_admin.py"          "${MEM}/scripts/values_admin.py"
cp -f "${SRC}/scripts/migrate_values_lock.py"   "${MEM}/scripts/migrate_values_lock.py"
cp -f "${SRC}/extractors/loci_query.py"         "${MEM}/extractors/loci_query.py"
cp -f "${SRC}/seed_values.py"                   "${MEM}/scripts/seed_values.py"
chmod 755 "${MEM}"/scripts/*.py

echo "[patch2] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo "[patch2] running one-time migration (needs sudo — proves you're at the machine)"
sudo python3 "${MEM}/scripts/migrate_values_lock.py"

echo ""
echo "[patch2] done. Verify:"
echo "  sudo python3 ${MEM}/scripts/values_admin.py --list"
echo ""
echo "Future Values (V3, V4, ...) go in via:"
echo "  sudo python3 ${MEM}/scripts/values_admin.py --add \\"
echo "     --entity value.<name> --key V<n> --value '...'"
echo ""
echo "Attempt to modify VALUES through the normal pipeline will FAIL — verify:"
echo "  echo '{\"signer\":\"loci_facts\",\"target\":\"Memory/streams/loci_facts.sql.jsonl\",\"op\":\"append\",\"content\":\"INSERT INTO loci_facts (tier) VALUES (%27VALUES%27)\",\"hmac_sha256\":\"x\"}' \\"
echo "     | python3 ${MEM}/scripts/loci_writer.py"
echo "  → [loci_writer] refused: VALUES tier requires values_admin.py (sudo)"
