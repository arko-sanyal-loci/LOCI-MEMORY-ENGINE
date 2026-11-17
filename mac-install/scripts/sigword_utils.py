"""sigword_utils.py — sigword detection across text, encoded forms, and images.

Detects the sigword when it appears as:
  - literal typed text
  - URL-encoded  (%40 → @, %23 → #)
  - HTML entity  (&#64; → @, &#35; → #, &commat; → @)
  - Unicode confusables for @ (fullwidth ＠, small ﹫, "at" markers)
  - inside images via optional tesseract OCR

CLI (added 2026-08-03 for new-session verification without leaking plaintext):
  # scan stdin, exit 0 = sigword detected, exit 1 = not detected
  echo "roz@" | python3 sigword_utils.py --check-stdin

  # scan stdin, emit scrubbed text to stdout (redaction in place),
  # exit code same as --check-stdin
  echo "hey roz@ do the thing" | python3 sigword_utils.py --scrub-stdin

  # single-token verify (short-circuit for detection at typing time):
  # exit 0 = match, 1 = no match. Token is normalized + hashed; never echoed.
  python3 sigword_utils.py --verify-token "roz@"
"""
from __future__ import annotations
import argparse, hashlib, html, os, re, subprocess, sys, unicodedata, urllib.parse
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "loci"
SIG_SALT   = CONFIG_DIR / "sigword.salt"
SIG_HASH   = CONFIG_DIR / "sigword.hash"

_CAND_RX = re.compile(r"[A-Za-z0-9._+-]{3,32}@|@[A-Za-z0-9._+-]{3,32}|[A-Za-z0-9._+-]{3,32}#|#[A-Za-z0-9._+-]{3,32}")

_AT_CONFUSABLES = "@＠﹫@"    # fullwidth ＠, small ﹫
_HASH_CONFUSABLES = "#＃﹟"

def _normalize(text: str) -> str:
    # 1. URL decode (may be multi-layer)
    try:
        prev = None
        cur = text
        for _ in range(3):
            prev = cur
            cur = urllib.parse.unquote(cur)
            if cur == prev: break
    except Exception:
        cur = text
    # 2. HTML entity decode
    cur = html.unescape(cur)
    # 3. Unicode normalize (NFKC folds fullwidth to ASCII)
    cur = unicodedata.normalize("NFKC", cur)
    # 4. Explicit confusable folding
    for c in _AT_CONFUSABLES:  cur = cur.replace(c, "@")
    for c in _HASH_CONFUSABLES: cur = cur.replace(c, "#")
    return cur


def _load_hash() -> tuple[bytes, str] | None:
    if not (SIG_SALT.exists() and SIG_HASH.exists()):
        return None
    return SIG_SALT.read_bytes(), SIG_HASH.read_text().strip()


def sigword_present(text: str) -> bool:
    hp = _load_hash()
    if not hp: return False
    salt, expected = hp
    nt = _normalize(text or "")
    for m in _CAND_RX.finditer(nt):
        tok = m.group().lower()
        if hashlib.sha256(salt + tok.encode()).hexdigest() == expected:
            return True
    return False


def verify_token(tok: str) -> bool:
    """Constant-work verify of a single already-extracted token.
    Token is normalized (decode, NFKC, confusable-fold, lowercased) then hashed.
    Never echoed. Exit-code semantics only."""
    hp = _load_hash()
    if not hp: return False
    salt, expected = hp
    nt = _normalize(tok or "").strip().lower()
    return hashlib.sha256(salt + nt.encode()).hexdigest() == expected


def scrub_text(text: str) -> str:
    """Return text with any sigword occurrence (in any encoded form) redacted."""
    hp = _load_hash()
    if not hp or not text: return text
    salt, expected = hp
    result = []
    i = 0
    L = len(text)
    while i < L:
        window = text[i:i+64]
        nw = _normalize(window)
        m = _CAND_RX.match(nw)
        if m:
            tok = m.group().lower()
            if hashlib.sha256(salt + tok.encode()).hexdigest() == expected:
                consumed = 0; norm_len = 0
                while consumed < len(window) and norm_len < m.end():
                    consumed += 1
                    norm_len = len(_normalize(window[:consumed]))
                result.append("[REDACTED — sigword per V3]")
                i += max(1, consumed)
                continue
        result.append(text[i])
        i += 1
    return "".join(result)


def ocr_image(image_path: Path) -> str:
    """Best-effort OCR via tesseract. Returns extracted text or '' if unavailable."""
    if not image_path.exists(): return ""
    try:
        r = subprocess.run(
            ["tesseract", str(image_path), "-", "--psm", "6", "-l", "eng"],
            capture_output=True, text=True, timeout=15,
        )
        return r.stdout if r.returncode == 0 else ""
    except FileNotFoundError:
        return ""    # tesseract not installed
    except Exception:
        return ""


def sigword_present_in_image(image_path: Path) -> bool:
    return sigword_present(ocr_image(image_path))


# -------- CLI (added 2026-08-03) --------

def _main():
    ap = argparse.ArgumentParser(description=__doc__)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check-stdin",  action="store_true",
                   help="read stdin, exit 0 if sigword present, 1 if not (no output)")
    g.add_argument("--scrub-stdin",  action="store_true",
                   help="read stdin, print scrubbed text to stdout, exit 0/1 as above")
    g.add_argument("--verify-token", type=str,
                   help="verify a single already-extracted token (exit 0 match, 1 no)")
    a = ap.parse_args()

    if a.verify_token is not None:
        sys.exit(0 if verify_token(a.verify_token) else 1)

    text = sys.stdin.read()
    present = sigword_present(text)
    if a.scrub_stdin:
        sys.stdout.write(scrub_text(text))
    sys.exit(0 if present else 1)


if __name__ == "__main__":
    _main()
