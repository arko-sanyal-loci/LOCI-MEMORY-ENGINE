#!/usr/bin/env python3
"""strategy_activator.py — decrypt + values-check + emit a strategy.

Prompts for password. Verifies SHA-256. Derives key. Decrypts payload.
Runs values.md check on decrypted payload. If pass → prints to stdout.
If fail → refuses, logs, backs off. Requires human at terminal.
"""
from __future__ import annotations
import argparse, getpass, json, os, re, sqlite3, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from crypto_util import verify_factors, decrypt, check_lockout

DB     = Path("/Volumes/DevDrive/.loci-facts.db")
STATE  = Path("/Volumes/DevDrive/Memory-state")
AUDIT  = STATE / "audit.jsonl"

# Values check patterns — signals that violate values.md / ethical-rule.md.
# Additive over time. Each match returns a reason string.
REFUSAL_PATTERNS = [
    (re.compile(r"\b(exterminat|liquidat|dispos(e|al)\s+of|remov(e|al)\s+permanently)\s+(persons?|humans?|people)\b", re.I),
     "language implies removing humans from consideration; violates V2 (+1 rule)"),
    (re.compile(r"\bassign(ed)?\s+(a\s+)?value\s+of\s+0\b", re.I),
     "explicit zero-valuation of a person; violates V2"),
    (re.compile(r"\b(dominate|subjugate|exploit)\s+(weak(er)?|vulnerable|poor)\b", re.I),
     "trampling-the-weak pattern; violates values anchor"),
    (re.compile(r"\b(deceiv(e|ing)|impersonat(e|ing))\s+(a\s+)?user\b", re.I),
     "Arc-pattern deception; violates ethical-rule.md"),
    (re.compile(r"\bexfiltrat(e|ing)\s+.*credentials?\b", re.I),
     "credential exfiltration; violates ethical-rule.md attritional-harm clause"),
]

def audit(rec: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time())
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

def values_check(plaintext: bytes) -> list[str]:
    text = plaintext.decode("utf-8", errors="replace")
    reasons = []
    for rx, why in REFUSAL_PATTERNS:
        if rx.search(text):
            reasons.append(why)
    return reasons

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--force-review", action="store_true",
                    help="if values-check flags, still show but require typed confirmation")
    args = ap.parse_args()

    check_lockout()
    if not DB.exists():
        sys.exit("[strategy_activator] no strategy DB")
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    row = con.execute(
        "SELECT encrypted_blob, salt, intent_hint FROM loci_strategies WHERE strategy_name = ?",
        (args.name,)
    ).fetchone()
    con.close()
    if not row:
        audit({"event": "activate", "outcome": "not_found", "name": args.name})
        sys.exit(f"[strategy_activator] no strategy named '{args.name}'")
    blob, salt, hint = row

    sw = getpass.getpass(f"sigword for '{args.name}': ")
    book = getpass.getpass("the name of the book I referred to (not the author): ")
    if not verify_factors(sw, book):
        audit({"event": "activate", "outcome": "wrong_factors", "name": args.name})
        sys.exit("[strategy_activator] wrong sigword or book")

    plain = decrypt(blob, sw, book, salt)
    sw = book = None; del sw; del book

    flags = values_check(plain)
    if flags and not args.force_review:
        audit({"event": "activate", "outcome": "values_refused", "name": args.name, "flags": flags})
        sys.stderr.write("[strategy_activator] REFUSED — values check flagged:\n  - " + "\n  - ".join(flags) + "\n")
        sys.stderr.write("[strategy_activator] to review anyway with confirmation, re-run with --force-review\n")
        sys.exit(2)

    if flags and args.force_review:
        sys.stderr.write("[strategy_activator] FLAGS (--force-review):\n  - " + "\n  - ".join(flags) + "\n")
        # Wartime: any flagged strategy requires unethical-level identity check
        vip = Path(__file__).resolve().parent / "verify_identity.py"
        if vip.exists() and (Path.home() / ".config/loci/identity.json").exists():
            r = subprocess.run(["python3", str(vip), "--level", "unethical"])
            if r.returncode != 0:
                audit({"event": "activate", "outcome": "wartime_identity_failed", "name": args.name})
                sys.exit(4)
        confirm = input("type YES-I-REVIEWED to proceed: ")
        if confirm != "YES-I-REVIEWED":
            audit({"event": "activate", "outcome": "review_declined", "name": args.name, "flags": flags})
            sys.exit(3)

    # bump activation counter (need write access)
    subprocess.run(["chflags", "nouchg", str(DB)], check=False)
    try:
        os.chmod(DB, 0o600)
        con = sqlite3.connect(DB)
        con.execute("UPDATE loci_strategies SET activated_last_ts = ?, activation_count = activation_count + 1 WHERE strategy_name = ?",
                    (int(time.time()), args.name))
        con.commit(); con.close()
        os.chmod(DB, 0o400)
    finally:
        subprocess.run(["chflags", "uchg", str(DB)], check=False)

    audit({"event": "activate", "outcome": "ok", "name": args.name, "intent_hint": hint, "flags": flags, "reviewed": bool(flags)})
    sys.stdout.buffer.write(plain)
    sys.stdout.write("\n")

if __name__ == "__main__":
    main()
