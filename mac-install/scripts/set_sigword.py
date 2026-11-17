#!/usr/bin/env python3
"""set_sigword.py — first-run sigword setup + rotation.

Prompts once (no echo). Writes:
  ~/.config/loci/sigword.salt   16 random bytes, chmod 400
  ~/.config/loci/sigword.hash   SHA-256(salt || lowercase(sigword)) hex, chmod 400

The plaintext sigword is NEVER stored. Verification at query time hashes the
candidate token with the same salt and compares.

Requires sudo (to write into ~/.config/loci with strict perms and to permit
scrubbing after rotation).
"""
from __future__ import annotations
import argparse, getpass, hashlib, os, subprocess, sys
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "loci"
SIG_SALT   = CONFIG_DIR / "sigword.salt"
SIG_HASH   = CONFIG_DIR / "sigword.hash"

def require_sudo():
    if os.geteuid() != 0:
        sys.exit("[set_sigword] run under sudo (writes to ~/.config/loci with strict perms).")

def prompt() -> str:
    s = getpass.getpass("sigword (no echo, will be lowercased): ").strip().lower()
    if not s: sys.exit("[set_sigword] empty")
    if len(s) < 3 or len(s) > 32: sys.exit("[set_sigword] length 3–32 chars")
    return s

def write(sw: str):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    salt = os.urandom(16)
    SIG_SALT.write_bytes(salt);  os.chmod(SIG_SALT, 0o400)
    SIG_HASH.write_text(hashlib.sha256(salt + sw.encode()).hexdigest())
    os.chmod(SIG_HASH, 0o400)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotate", action="store_true")
    args = ap.parse_args()
    require_sudo()
    if SIG_SALT.exists() and not args.rotate:
        sys.exit("[set_sigword] already set. Use --rotate to change.")
    sw = prompt()
    write(sw)
    print(f"[set_sigword] ok. Salt+hash at {CONFIG_DIR}/ (chmod 400).")
    print("[set_sigword] scrub existing occurrences with:")
    print("  sudo python3 /Volumes/DevDrive/Memory/scripts/scrub_sigword.py --target /Volumes/DevDrive/Memory --relock")
    print("  sudo python3 /Volumes/DevDrive/Memory/scripts/scrub_sigword.py --target /Volumes/DevDrive/Transcripts --relock")

if __name__ == "__main__":
    main()
