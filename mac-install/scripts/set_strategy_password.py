#!/usr/bin/env python3
"""set_strategy_password.py — first-run password setup + rotation.

Prompts twice (no echo). Writes:
  ~/.config/loci/strategy.salt   16 random bytes, chmod 400
  ~/.config/loci/strategy.hash   SHA-256(salt || password) hex, chmod 400

--rotate: re-encrypt every existing loci_strategies row with the new password.
"""
from __future__ import annotations
import argparse, base64, getpass, hashlib, os, sqlite3, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crypto_util import (
    SALT_PATH, HASH_PATH, CONFIG_DIR, ensure_config_dir,
    derive_key, fernet_from_key,
)

DB = Path("/Volumes/DevDrive/.loci-facts.db")

def prompt_new() -> str:
    p1 = getpass.getpass("new strategy password: ")
    p2 = getpass.getpass("confirm:              ")
    if p1 != p2:
        sys.exit("passwords didn't match")
    if len(p1) < 12:
        sys.exit("password must be ≥12 chars")
    return p1

def write_password(pw: str) -> bytes:
    ensure_config_dir()
    salt = os.urandom(16)
    SALT_PATH.write_bytes(salt);  os.chmod(SALT_PATH, 0o400)
    h = hashlib.sha256(salt + pw.encode()).hexdigest()
    HASH_PATH.write_text(h);      os.chmod(HASH_PATH, 0o400)
    return salt

def rotate():
    if not SALT_PATH.exists():
        sys.exit("no existing password to rotate; run without --rotate for first-time setup")
    old = getpass.getpass("current password: ")
    old_salt = SALT_PATH.read_bytes()
    if hashlib.sha256(old_salt + old.encode()).hexdigest() != HASH_PATH.read_text().strip():
        sys.exit("current password wrong")
    new = prompt_new()

    if DB.exists():
        # unlock DB, re-encrypt every row, re-lock
        import subprocess
        subprocess.run(["chflags", "nouchg", str(DB)], check=False)
        try:
            os.chmod(DB, 0o600)
            con = sqlite3.connect(DB); cur = con.cursor()
            rows = cur.execute("SELECT id, salt, encrypted_blob FROM loci_strategies").fetchall()
            for row_id, row_salt, blob in rows:
                key_old = derive_key(old, row_salt)
                plain = fernet_from_key(key_old).decrypt(blob)
                new_salt = os.urandom(16)
                key_new = derive_key(new, new_salt)
                new_blob = fernet_from_key(key_new).encrypt(plain)
                cur.execute("UPDATE loci_strategies SET salt=?, encrypted_blob=? WHERE id=?",
                            (new_salt, new_blob, row_id))
            con.commit(); con.close()
            os.chmod(DB, 0o400)
        finally:
            subprocess.run(["chflags", "uchg", str(DB)], check=False)

    write_password(new)
    print(f"[set_strategy_password] rotated. {len(rows) if DB.exists() else 0} rows re-encrypted.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotate", action="store_true")
    args = ap.parse_args()
    if args.rotate: return rotate()
    if SALT_PATH.exists():
        sys.exit(f"password already set at {SALT_PATH}. Use --rotate to change.")
    pw = prompt_new()
    write_password(pw)
    print(f"[set_strategy_password] password set. salt+hash at {CONFIG_DIR}/ (chmod 400).")

if __name__ == "__main__":
    main()
