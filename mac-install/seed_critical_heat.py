#!/usr/bin/env python3
"""
seed_critical_heat.py — insert a life-turning event as tier=CRITICAL_HEAT.

Usage:
  python3 seed_critical_heat.py \
      --entity "family.first_child" --key "birth" \
      --value "Daughter born, Dhaka" --date "2027-04-12"

--date is required (determines source_ts; drives the 5-year half-life decay).
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SIGN = HERE / "scripts" / "sign_patch.py"
WRITER = Path("/Volumes/DevDrive/Memory/scripts/loci_writer.py")
COMMIT = Path("/Volumes/DevDrive/Memory/extractors/loci_facts_extractor.py")
TARGET_REL = "Memory/streams/loci_facts.sql.jsonl"

def to_ts(s: str) -> int:
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y/%m/%d"):
        try: return int(time.mktime(time.strptime(s, fmt)))
        except: pass
    sys.exit(f"[seed_critical_heat] unrecognized date: {s}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entity", required=True)
    ap.add_argument("--key",    required=True)
    ap.add_argument("--value",  required=True)
    ap.add_argument("--date",   required=True, help="event date (YYYY-MM-DD)")
    args = ap.parse_args()

    src_ts = to_ts(args.date)
    now = int(time.time())
    op = {
        "sql": (
            "INSERT INTO loci_facts (entity,key,value,value_type,embedding,"
            "source_trust,source_session,source_ts,heat,last_access_ts,"
            "version,prev_version_id,superseded_by,tier,created_ts,updated_ts) "
            "VALUES (?,?,?,?,NULL,?,?,?,?,?,1,NULL,NULL,'CRITICAL_HEAT',?,?)"
        ),
        "params": [args.entity, args.key, args.value, "life_event",
                   1.0, "seed_critical_heat", src_ts,
                   100.0, now,   # baseline heat; loci_query recomputes with 5y decay at read
                   now, now],
    }
    content = json.dumps(op, sort_keys=True) + "\n"
    patch = {"signer": "loci_facts", "target": TARGET_REL, "op": "append", "content": content}

    p = subprocess.run(["python3", str(SIGN)], input=json.dumps(patch), capture_output=True, text=True, check=True)
    r = subprocess.run(["python3", str(WRITER)], input=p.stdout, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"[seed_critical_heat] writer refused: {r.stderr}")
    r2 = subprocess.run(["python3", str(COMMIT)], capture_output=True, text=True)
    print(r2.stderr, file=sys.stderr)
    print(f"[seed_critical_heat] {args.entity}/{args.key} = {args.value!r} (source_ts={args.date}) seeded as CRITICAL_HEAT.")

if __name__ == "__main__":
    main()
