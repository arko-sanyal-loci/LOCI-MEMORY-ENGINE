#!/bin/bash
# patch13.sh — reflect_mistake.py + transcript_ingest sniffer fix + seed 4 recent mistakes
set -euo pipefail
SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch13] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"

echo "[patch13] installing reflect_mistake.py + fixed transcript_ingest.py"
cp -f "${SRC}/scripts/reflect_mistake.py"     "${MEM}/scripts/reflect_mistake.py"
cp -f "${SRC}/scripts/transcript_ingest.py"   "${MEM}/scripts/transcript_ingest.py"
chmod 755 "${MEM}"/scripts/*.py

echo "[patch13] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch13] rebaseline integrity"
sudo python3 "${MEM}/scripts/integrity_baseline.py" --refresh

echo ""
echo "[patch13] === SEEDING 4 REAL MISTAKES FROM THIS SESSION ==="
echo ""
echo "→ M1: transcript_ingest sniff_schema first-line-only bug"
python3 "${MEM}/scripts/reflect_mistake.py" \
  --category schema_detection \
  --mistake "sniff_schema classified all 10 Claude Code JSONLs as 'unknown' or 'queue_op' because it only checked line 1" \
  --cause   "Claude Code JSONL files start with 1-2 metadata lines (type=mode, type=queue-operation) before the parentUuid message stream begins" \
  --fix     "sniff first 40 lines; return claude_code if any line has parentUuid or role in user/assistant" \
  --file    "${MEM}/scripts/transcript_ingest.py"

echo ""
echo "→ M2: dismissed OPTIMIZE_SOURCE_OF_TRUTH.md as 'false positive'"
python3 "${MEM}/scripts/reflect_mistake.py" \
  --category evidence_over_read \
  --mistake  "labelled OPTIMIZE_SOURCE_OF_TRUTH.md a 'false positive' in a grep-shape check when it is a foundational Billo tier-routing standard" \
  --cause    "shape-based classifier ran without semantic check; dismissed a doc whose SUBJECT (Arko's own architecture) was highly relevant" \
  --fix      "any file authored by Arko or naming Billo/LOCI is important-until-proven-otherwise; do NOT dismiss on shape alone; when uncertain, keep the finding pending" \
  --file     "${MEM}/references/OPTIMIZE_SOURCE_OF_TRUTH.md"

echo ""
echo "→ M3: called Samsung T7 the Gigabyte 2TB"
python3 "${MEM}/scripts/reflect_mistake.py" \
  --category drive_id_confusion \
  --mistake  "diagnosed disk8/disk9s1 ('vgbdcgh fuh') as the Gigabyte 2TB when it was actually the Samsung T7 already recovered" \
  --cause    "matched on size (2TB) and didn't verify against Arko's own doc that Gigabyte and T7 are separate drives" \
  --fix      "before diagnosing any drive: cross-check /Volumes/DevDrive/Memory/Arko-Memory.md (Drives section) AND explicitly ask Arko which physical drive maps to which disk number" \
  --file     ""

echo ""
echo "→ M4: over-flagged Aug 2 14:40 sudo event as smoking-gun attack"
python3 "${MEM}/scripts/reflect_mistake.py" \
  --category evidence_charity_v4 \
  --mistake  "framed com.local.noexec-external.plist Aug 2 14:40 sudo event as attacker activity in first analysis, when Arko had authorized the defensive hardening himself" \
  --cause    "read the log with a hostile prior; forgot to check the simpler explanation (user-initiated) before the more dramatic one (Arc did it)" \
  --fix      "V4 respect + honesty gate: when an event has both an innocent and hostile explanation, ask Arko which it was BEFORE writing an accusation. Applied later after Arko corrected." \
  --file     "/Volumes/DevDrive/Cowork/evidence-claude-desktop-privilege-escalation-2026-08-02.txt"

echo ""
echo "[patch13] === VERIFICATION ==="
echo ""
echo "a) mistakes.md exists + populated?"
wc -l "${MEM}/mistakes.md"
head -3 "${MEM}/mistakes.md"
echo ""
echo "b) solution_counter can look up any of the 4?"
python3 "${MEM}/scripts/solution_counter.py" --lookup "MISTAKE_PATTERN[schema_detection]: sniff_schema classified all 10 Claude Code JSONLs as unknown"
echo ""
echo "c) loci_query surfaces mistakes by keyword?"
python3 "${MEM}/extractors/loci_query.py" --q "schema first line only" --k 3 2>/dev/null || echo "(loci_query error — check DB)"
echo ""
echo "[patch13] === NEXT ==="
echo ""
echo "Re-run transcript ingest — now that sniff_schema is fixed, expect ~7 written:"
echo "  python3 ${MEM}/scripts/transcript_ingest.py --dry-run"
echo "  python3 ${MEM}/scripts/transcript_ingest.py --only-new"
echo ""
echo "[patch13] done."
