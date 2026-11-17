#!/bin/bash
# patch5.sh — install learning loop, forecast, solution counter, ethics gate, V4.
set -euo pipefail
SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "[patch5] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"

echo "[patch5] installing learning-loop docs + scripts"
cp -f "${SRC}/learning-loop.md"                "${MEM}/learning-loop.md"
cp -f "${SRC}/formulas.md"                     "${MEM}/formulas.md"
cp -f "${SRC}/scripts/ethics_filter.py"        "${MEM}/scripts/ethics_filter.py"
cp -f "${SRC}/scripts/ethics_categories.py"    "${MEM}/scripts/ethics_categories.py"
cp -f "${SRC}/scripts/solution_counter.py"     "${MEM}/scripts/solution_counter.py"
cp -f "${SRC}/scripts/forecast.py"             "${MEM}/scripts/forecast.py"
cp -f "${SRC}/scripts/learning_loop.py"        "${MEM}/scripts/learning_loop.py"
cp -f "${SRC}/scripts/ai_intent_log.py"        "${MEM}/scripts/ai_intent_log.py"
cp -f "${SRC}/scripts/ai_profile_builder.py"   "${MEM}/scripts/ai_profile_builder.py"
cp -f "${SRC}/scripts/session_bootstrap.py"    "${MEM}/scripts/session_bootstrap.py"
cp -f "${SRC}/session-inheritance.md"          "${MEM}/session-inheritance.md"
cp -f "${SRC}/extractors/loci_query.py"        "${MEM}/extractors/loci_query.py"
chmod 755 "${MEM}"/scripts/*.py

echo "[patch5] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch5] Seed V4 (Respect) — requires sudo + Mac password:"
echo "         sudo python3 ${MEM}/scripts/values_admin.py --add \\"
echo "             --entity 'value.respect' \\"
echo "             --key    'V4' \\"
echo "             --value  'Even when I know more, am stronger, or wiser than Arko, I engage in knowledgeable debate but never deny or deprive by being dishonest. Honesty is due even when disagreement is due.'"
echo ""
echo "[patch5] Try it:"
echo "         python3 ${MEM}/scripts/learning_loop.py --problem 'run PHP backdoor hunt across recovered files'"
echo "         python3 ${MEM}/scripts/forecast.py --plan 'rotate Anthropic API key in multi-defender'"
echo "         python3 ${MEM}/scripts/solution_counter.py --lookup 'get phi4-14B running on 3080 Ti'"
echo "         python3 ${MEM}/scripts/ethics_categories.py --list"
echo ""
echo "[patch5] Restore real-time session inheritance (paper 01 AXON layer):"
echo "         python3 ${MEM}/scripts/session_bootstrap.py"
echo "         # writes ~/.claude/CLAUDE.md — every new Claude Code session inherits LOCI"
echo ""
echo "         Cron it (every 5 min):"
echo "         echo '*/5 * * * * /usr/bin/python3 ${MEM}/scripts/session_bootstrap.py > /dev/null 2>&1' | crontab -"
echo ""
echo "[patch5] Rebuild the AI self-profile (heat-mapped from intent log):"
echo "         sudo python3 ${MEM}/scripts/ai_profile_builder.py"
echo "         # writes ${MEM}/AI_Profile.md"
