#!/usr/bin/env python3
"""unlock_segment.py — decrypt a locked transcript segment.

Usage:
  python3 unlock_segment.py <uuid>
  (prompts for sigword; on success prints plaintext to stdout)
"""
from __future__ import annotations
import base64, getpass, hashlib, sys
from pathlib import Path

try:
    from cryptography.fernet import Fernet, InvalidToken
except Exception:
    sys.exit("[unlock] pip3 install cryptography (or --user)")

VAULT = Path("/Volumes/DevDrive/.locked-segments")
SIG_SALT = Path.home() / ".config" / "loci" / "sigword.salt"
SIG_HASH = Path.home() / ".config" / "loci" / "sigword.hash"
PBKDF2_ITERS = 600_000

def main():
    if len(sys.argv) != 2:
        sys.exit("usage: unlock_segment.py <uuid>")
    uid = sys.argv[1]
    blob_path = VAULT / f"{uid}.enc"
    if not blob_path.exists():
        sys.exit(f"[unlock] not found: {blob_path}")
    if not (SIG_SALT.exists() and SIG_HASH.exists()):
        sys.exit("[unlock] no sigword set")
    sw = getpass.getpass("sigword: ").strip().lower()
    if hashlib.sha256(SIG_SALT.read_bytes() + sw.encode()).hexdigest() != SIG_HASH.read_text().strip():
        sys.exit("[unlock] wrong sigword")

    data = blob_path.read_bytes()
    seg_salt, ct = data[:16], data[16:]
    key = hashlib.pbkdf2_hmac("sha256", sw.encode(), seg_salt, PBKDF2_ITERS, dklen=32)
    f = Fernet(base64.urlsafe_b64encode(key))
    try:
        pt = f.decrypt(ct)
    except InvalidToken:
        sys.exit("[unlock] wrong sigword (fernet said no)")
    sys.stdout.buffer.write(pt); sys.stdout.write("\n")

if __name__ == "__main__":
    main()
