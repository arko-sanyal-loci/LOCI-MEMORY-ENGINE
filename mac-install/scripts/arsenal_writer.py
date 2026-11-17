#!/usr/bin/env python3
"""arsenal_writer.py — write a tier='ARSENAL' record to loci_facts.

HMAC-signed like other loci_facts inserts. Values check runs at write time:
if the arsenal item's value string matches a REFUSAL_PATTERN from
strategy_activator, the write is refused.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from strategy_activator import REFUSAL_PATTERNS

SIGN = HERE / "sign_patch.py"
WRITER = Path("/Volumes/DevDrive/Memory/scripts/loci_writer.py")
COMMIT = Path("/Volumes/DevDrive/Memory/extractors/loci_facts_extractor.py")
TARGET_REL = "Memory/streams/loci_facts.sql.jsonl"

def check(text: str) -> list[str]:
    return [why for rx, why in REFUSAL_PATTERNS if rx.search(text)]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entity", required=True)
    ap.add_argument("--key",    required=True)
    ap.add_argument("--value",  required=True)
    ap.add_argument("--source", default="arsenal_writer")
    args = ap.parse_args()

    flags = check(args.value + " " + args.entity + " " + args.key)
    if flags:
        sys.stderr.write("[arsenal_writer] REFUSED — values check flagged:\n  - " + "\n  - ".join(flags) + "\n")
        sys.exit(2)

    now = int(time.time())
    op = {
        "sql": (
            "INSERT INTO loci_facts (entity,key,value,value_type,embedding,"
            "source_trust,source_session,source_ts,heat,last_access_ts,"
            "version,prev_version_id,superseded_by,tier,created_ts,updated_ts) "
            "VALUES (?,?,?,?,NULL,?,?,?,?,?,1,NULL,NULL,'ARSENAL',?,?)"
        ),
        "params": [args.entity, args.key, args.value, "capability",
                   1.0, args.source, now,
                   1.0, now,
                   now, now],
    }
    content = json.dumps(op, sort_keys=True) + "\n"
    patch = {"signer": "loci_facts", "target": TARGET_REL, "op": "append", "content": content}

    p = subprocess.run(["python3", str(SIGN)], input=json.dumps(patch), capture_output=True, text=True, check=True)
    r = subprocess.run(["python3", str(WRITER)], input=p.stdout, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"[arsenal_writer] writer refused: {r.stderr}")
    r2 = subprocess.run(["python3", str(COMMIT)], capture_output=True, text=True)
    print(r2.stderr, file=sys.stderr)
    print(f"[arsenal_writer] {args.entity}/{args.key} seeded as ARSENAL.")

if __name__ == "__main__":
    main()
