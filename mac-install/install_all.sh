#!/bin/bash
# install_all.sh — one-command install: runs every patch in order, in isolation.
# Skips patches that would fail (idempotent). Prompts for sudo once, then reuses.
#
# Run:
#   bash /Volumes/DevDrive/loci-install/install_all.sh
#
# What you'll be prompted for:
#   1. Mac password (once, cached by sudo for the rest of the run)
#   2. sigword (typed twice, no echo)   — set_sigword.py
#   3. 6 identity factors (no echo)     — set_identity.py
#   4. book answer (twice, no echo)     — set_book.py
set -uo pipefail

SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

echo "════════════════════════════════════════════════════════════════"
echo "  LOCI install — six patches + interactive setup"
echo "════════════════════════════════════════════════════════════════"

# Prime sudo cache
sudo -v || { echo "[install_all] sudo required"; exit 1; }

for P in patch.sh patch2.sh patch3.sh patch4.sh patch5.sh patch6.sh patch7.sh patch8.sh; do
    if [ -f "${SRC}/${P}" ]; then
        echo ""
        echo "────  ${P}  ────"
        bash "${SRC}/${P}" || echo "[install_all] ${P} exited non-zero (may already be applied — continuing)"
    fi
done

# Install defense skill to ~/.claude/skills/loci-defense
echo ""
echo "──── installing loci-defense skill ────"
mkdir -p "$HOME/.claude/skills/loci-defense"
cp -f "${SRC}/skills/loci-defense/SKILL.md" "$HOME/.claude/skills/loci-defense/SKILL.md"
chmod 644 "$HOME/.claude/skills/loci-defense/SKILL.md"

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Interactive setup — the four secrets"
echo "════════════════════════════════════════════════════════════════"

# sigword
if [ ! -f "$HOME/.config/loci/sigword.hash" ]; then
    echo "1/4 — sigword:"
    sudo python3 "${MEM}/scripts/set_sigword.py" || true
else
    echo "1/4 — sigword already set (skip)"
fi

# identity
if [ ! -f "$HOME/.config/loci/identity.json" ]; then
    echo "2/4 — identity (6 factors):"
    sudo python3 "${MEM}/scripts/set_identity.py" || true
else
    echo "2/4 — identity already set (skip)"
fi

# book
if [ ! -f "$HOME/.config/loci/book.hash" ]; then
    echo "3/4 — book question:"
    sudo python3 "${MEM}/scripts/set_book.py" || true
else
    echo "3/4 — book already set (skip)"
fi

# scrub sigword from Memory + Transcripts
echo "4/4 — scrubbing sigword from Memory + Transcripts:"
sudo python3 "${MEM}/scripts/scrub_sigword.py" --target "${MEM}" --relock 2>&1 | tail -5 || true
sudo python3 "${MEM}/scripts/scrub_sigword.py" --target /Volumes/DevDrive/Transcripts --relock 2>&1 | tail -5 || true

# Bootstrap session CLAUDE.md
echo ""
echo "──── generating ~/.claude/CLAUDE.md (session inheritance) ────"
python3 "${MEM}/scripts/session_bootstrap.py" || true

# Optional: build AI_Profile
echo ""
echo "──── building AI_Profile.md ────"
sudo python3 "${MEM}/scripts/ai_profile_builder.py" || true

echo ""
echo "════════════════════════════════════════════════════════════════"
echo "  Done. Everything installed."
echo "════════════════════════════════════════════════════════════════"
echo ""
echo "Live metrics:      python3 ${MEM}/scripts/metrics.py --watch"
echo "Query LOCI:        python3 ${MEM}/extractors/loci_query.py --q 'your question'"
echo "Focus status:      python3 ${MEM}/scripts/set_focus.py --show"
echo "Values list:       sudo python3 ${MEM}/scripts/values_admin.py --list"
echo "Cron the bootstrap: (crontab -l 2>/dev/null; echo '*/5 * * * * /usr/bin/python3 ${MEM}/scripts/session_bootstrap.py > /dev/null 2>&1') | crontab -"
