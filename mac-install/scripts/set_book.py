#!/usr/bin/env python3
"""set_book.py — set (or rotate) the book-question factor for strategy activation.

The book-answer, together with the sigword, forms the two-factor key for
strategies (see strategies.md). Answer is normalized (lowercase, strip
diacritics, collapse whitespace) then SHA-256(salt||answer) is stored.
Plaintext never written.

Requires sudo.
"""
from __future__ import annotations
import argparse, getpass, hashlib, os, sys, unicodedata
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "loci"
BOOK_SALT  = CONFIG_DIR / "book.salt"
BOOK_HASH  = CONFIG_DIR / "book.hash"

CHALLENGE_PROMPT = "the name of the book I referred to (not the author, no article, lowercase): "

def require_sudo():
    if os.geteuid() != 0:
        sys.exit("[set_book] run under sudo")

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return " ".join(s.strip().lower().split())

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotate", action="store_true")
    args = ap.parse_args()
    require_sudo()
    if BOOK_SALT.exists() and not args.rotate:
        sys.exit(f"[set_book] already set at {BOOK_SALT}. Use --rotate to change.")

    a1 = normalize(getpass.getpass(CHALLENGE_PROMPT))
    a2 = normalize(getpass.getpass("confirm: "))
    if a1 != a2 or not a1:
        sys.exit("[set_book] mismatch or empty")

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    salt = os.urandom(16)
    BOOK_SALT.write_bytes(salt);          os.chmod(BOOK_SALT, 0o400)
    BOOK_HASH.write_text(hashlib.sha256(salt + a1.encode()).hexdigest())
    os.chmod(BOOK_HASH, 0o400)
    # discard plaintext
    a1 = a2 = None
    print(f"[set_book] stored hash at {BOOK_HASH} (chmod 400). Plaintext discarded.")

if __name__ == "__main__":
    main()
