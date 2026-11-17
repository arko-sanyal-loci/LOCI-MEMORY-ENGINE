#!/usr/bin/env python3
"""strategy_writer.py — encrypt + store a strategy payload.

Prompts for password (no echo). Uses PBKDF2+Fernet from crypto_util. Stores
into loci_strategies table in /Volumes/DevDrive/.loci-facts.db (temp unlock).

Payload can come from --file or stdin.
"""
from __future__ import annotations
import argparse, getpass, os, sqlite3, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crypto_util import verify_factors, encrypt, check_lockout

DB = Path("/Volumes/DevDrive/.loci-facts.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS loci_strategies (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_name         TEXT UNIQUE NOT NULL,
    encrypted_blob        BLOB NOT NULL,
    salt                  BLOB NOT NULL,
    intent_hint           TEXT,
    created_ts            INTEGER,
    activated_last_ts     INTEGER,
    activation_count      INTEGER DEFAULT 0,
    values_review_status  TEXT DEFAULT 'unreviewed'
);
CREATE INDEX IF NOT EXISTS ix_strat_name ON loci_strategies(strategy_name);
"""

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--intent-hint", required=True, help="short plaintext description (audit-visible)")
    ap.add_argument("--file", type=Path, help="payload file (default: stdin)")
    args = ap.parse_args()

    check_lockout()
    sw = getpass.getpass("sigword: ")
    book = getpass.getpass("the name of the book I referred to (not the author): ")
    if not verify_factors(sw, book):
        sys.exit("[strategy_writer] wrong sigword or book")

    payload = args.file.read_bytes() if args.file else sys.stdin.buffer.read()
    if not payload:
        sys.exit("[strategy_writer] empty payload")

    salt = os.urandom(16)
    blob = encrypt(payload, sw, book, salt)
    now = int(time.time())

    subprocess.run(["chflags", "nouchg", str(DB)], check=False)
    try:
        os.chmod(DB, 0o600)
        con = sqlite3.connect(DB); cur = con.cursor()
        cur.executescript(SCHEMA)
        cur.execute(
            "INSERT OR REPLACE INTO loci_strategies "
            "(strategy_name, encrypted_blob, salt, intent_hint, created_ts, activation_count) "
            "VALUES (?,?,?,?,?,0)",
            (args.name, blob, salt, args.intent_hint, now),
        )
        con.commit(); con.close()
        os.chmod(DB, 0o400)
    finally:
        subprocess.run(["chflags", "uchg", str(DB)], check=False)

    sw = book = None; del sw; del book
    print(f"[strategy_writer] stored '{args.name}' ({len(payload)} B plaintext → {len(blob)} B ciphertext). intent_hint audited.")

if __name__ == "__main__":
    main()
