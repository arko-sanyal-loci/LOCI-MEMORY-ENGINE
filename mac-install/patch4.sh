#!/bin/bash
# patch4.sh — install lock_segments + unlock_segment, then lock the identity-
# design segments from this session's transcript.
set -euo pipefail

SRC="/Volumes/DevDrive/loci-install"
MEM="/Volumes/DevDrive/Memory"

if [ ! -f "$HOME/.config/loci/sigword.hash" ]; then
    echo "[patch4] sigword not set — run first:  sudo python3 ${MEM}/scripts/set_sigword.py"
    exit 1
fi

echo "[patch4] unlocking Memory/"
sudo chflags -R nouchg "${MEM}"
echo "[patch4] copying lock/unlock + set_book + updated crypto/strategy scripts + metrics + updated loci_query"
cp -f "${SRC}/scripts/lock_segments.py"      "${MEM}/scripts/lock_segments.py"
cp -f "${SRC}/scripts/unlock_segment.py"     "${MEM}/scripts/unlock_segment.py"
cp -f "${SRC}/scripts/set_book.py"           "${MEM}/scripts/set_book.py"
cp -f "${SRC}/scripts/crypto_util.py"        "${MEM}/scripts/crypto_util.py"
cp -f "${SRC}/scripts/strategy_writer.py"    "${MEM}/scripts/strategy_writer.py"
cp -f "${SRC}/scripts/strategy_activator.py" "${MEM}/scripts/strategy_activator.py"
cp -f "${SRC}/scripts/metrics.py"            "${MEM}/scripts/metrics.py"
cp -f "${SRC}/scripts/profile_check.py"      "${MEM}/scripts/profile_check.py"
cp -f "${SRC}/Arko_Profile.md"               "${MEM}/Arko_Profile.md"
cp -f "${SRC}/extractors/loci_query.py"      "${MEM}/extractors/loci_query.py"
# deprecate old set_strategy_password.py — it's superseded by set_sigword+set_book
if [ -e "${MEM}/scripts/set_strategy_password.py" ]; then
    sudo chflags nouchg "${MEM}/scripts/set_strategy_password.py"
    sudo rm -f "${MEM}/scripts/set_strategy_password.py"
fi
chmod 755 "${MEM}"/scripts/*.py
echo "[patch4] re-locking Memory/"
sudo find "${MEM}" -type f -exec chflags uchg {} \;
sudo find "${MEM}" -type d -exec chflags uchg {} \;

echo ""
echo "[patch4] discovering current-session transcript..."
CUR=$(ls -td /Volumes/DevDrive/Transcripts/*/local_*/  2>/dev/null | head -1 | sed 's:/$::')
echo "[patch4] target session dir: ${CUR}"
JSONLS=$(find "${CUR}" -name "*.jsonl" -not -name "audit.jsonl" 2>/dev/null)
AUDIT=$(find "${CUR}" -name "audit.jsonl" 2>/dev/null | head -1)

echo ""
echo "[patch4] locking sensitive segments in transcripts (prompts for sigword)..."
echo "         Sun Tzu (author) stays visible in transcripts as decoy per your instruction."
echo "         Art of War (the answer) + identity mappings + decoy-disclosure sentences get locked."
for J in ${JSONLS} ${AUDIT}; do
    [ -z "$J" ] && continue
    echo "  target: $J"
    sudo python3 "${MEM}/scripts/lock_segments.py" \
        --target "$J" \
        --pattern 'Cats?[ ]?name[ ]?\(' \
        --pattern 'Wife[ ]?\(' \
        --pattern 'Wifes[ ]?name[ ]?\(' \
        --pattern 'My[ ]?Phone[ ]?Number' \
        --pattern 'My[ ]?Dogs?[ ]?Name' \
        --pattern 'My[ ]?Mothers?[ ]?Name' \
        --pattern 'My[ ]?Fathers?[ ]?Name' \
        --pattern '[Aa]rt of [Ww]ar' \
        --pattern 'book I referred to' \
        --pattern 'name of the book' \
        --pattern '[Aa]uthors?[ ]?name[ ]+as[ ]+(?:the[ ]+)?decoy' \
        --pattern 'sigword[ ]?\+[ ]?book' \
        --pattern 'book[ ]?\+[ ]?sigword' \
        --pattern 'two-factor.+(?:sigword|book)' \
        --pattern '(?:sigword|book).+two-factor'
done

echo ""
echo "[patch4] done. Locked blobs at /Volumes/DevDrive/.locked-segments/  (chmod 400, uchg)"
echo "         To decrypt any segment:  python3 ${MEM}/scripts/unlock_segment.py <uuid>"
echo ""
echo "[patch4] Set the book-question factor for strategy activation:"
echo "         sudo python3 ${MEM}/scripts/set_book.py"
echo "         (from now on strategies unlock with sigword + book — no separate password)"
echo ""
echo "[patch4] NOTE: This locked messages written up to the current moment. Anything typed"
echo "         after this point in the still-running session will be appended un-locked."
echo "         RE-RUN patch4.sh (or just lock_segments.py) after the session ends to catch"
echo "         the rest. Idempotent — already-locked segments are skipped."
echo ""
echo "[patch4] Real-time metrics — anytime:"
echo "         python3 ${MEM}/scripts/metrics.py --show      # snapshot"
echo "         python3 ${MEM}/scripts/metrics.py --watch     # live (refresh every 2s)"
echo "         sudo python3 ${MEM}/scripts/metrics.py --reset  # zero counters"
