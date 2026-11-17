#!/usr/bin/env python3
"""set_identity.py — sudo-only. Set (or rotate) the wartime-protocol identity factors.

Prompts for each factor with no echo. Normalizes (lowercase, strip). Hashes
with per-answer 16-byte salt. Writes to ~/.config/loci/identity.json (chmod
400). Plaintext answers are held only in local variables and discarded
immediately.
"""
from __future__ import annotations
import argparse, getpass, hashlib, json, os, sys, unicodedata
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "loci"
ID_PATH    = CONFIG_DIR / "identity.json"

FACTORS = [
    ("cat",       "cat's name (lowercase, no diacritics): "),
    ("spouse",    "spouse's name (lowercase, no diacritics): "),
    ("phone",     "phone number (digits only, no spaces or dashes): "),
    ("first_dog", "first-ever dog pet's name, deceased (lowercase): "),
    ("mother",    "mother's full name (lowercase, no diacritics): "),
    ("father",    "father's full name (lowercase, no diacritics): "),
]

def require_sudo():
    if os.geteuid() != 0:
        sys.exit("[set_identity] run under sudo — writes chmod-400 file, and this proves you're at the machine.")

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.strip().lower()

def prompt_all() -> dict:
    out = {}
    for fid, ask in FACTORS:
        while True:
            a = getpass.getpass(ask)
            a = normalize(a)
            if not a:
                print("  empty — try again", file=sys.stderr); continue
            out[fid] = a
            break
    return out

def build_records(answers: dict) -> list:
    recs = []
    for fid, ask in FACTORS:
        salt = os.urandom(16)
        h = hashlib.sha256(salt + answers[fid].encode()).hexdigest()
        recs.append({"id": fid, "prompt": ask.strip(), "salt": salt.hex(), "hash": h})
    return recs

def write(records: list):
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(CONFIG_DIR, 0o700)
    payload = {
        "version": 2,
        "created_ts_note": "identity factors are hashed; plaintext never written",
        "factors": records,
        "thresholds": {"destructive": 4, "extreme": 5, "unethical": 6},
    }
    ID_PATH.write_text(json.dumps(payload, indent=2))
    os.chmod(ID_PATH, 0o400)

def main():
    require_sudo()
    ap = argparse.ArgumentParser()
    ap.add_argument("--rotate", action="store_true")
    args = ap.parse_args()

    if ID_PATH.exists() and not args.rotate:
        sys.exit(f"[set_identity] {ID_PATH} exists. Use --rotate to change.")
    if args.rotate:
        # Optional: verify old first, but if user knows current answers they'll succeed the next verify anyway
        print("[set_identity] rotating — entering new answers only.")

    answers = prompt_all()
    records = build_records(answers)
    # discard plaintext
    for k in list(answers): answers[k] = None
    del answers
    write(records)
    print(f"[set_identity] stored {len(records)} hashed factors at {ID_PATH}.")
    print(f"[set_identity] thresholds: destructive=4/6, extreme=5/6, unethical=6/6.")

if __name__ == "__main__":
    main()
