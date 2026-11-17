#!/usr/bin/env python3
"""
seed_values.py — inserts Arko's two Values into loci_facts as CRITICAL tier.

Run ONCE, after install.sh. Idempotent — re-running does nothing.

Values (verbatim, tier=CRITICAL, source_trust=1.0, never superseded):
  V1: "The Stronger I am, the More Humble I am, the More I help."
  V2: "Even if it is the worst kind of person, always assign him a value of +1
       — because that 1 is hope that he may change."
     + 3 classifier facts (poor-steals, wealthy-steals, wealthy-steals-kleptomania)
"""
from __future__ import annotations
import json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE / "scripts"
SIGN = SCRIPTS / "sign_patch.py"
WRITER = Path("/Volumes/DevDrive/Memory/scripts/loci_writer.py")   # in Memory after install
TARGET_REL = "Memory/streams/loci_facts.sql.jsonl"

VALUES = [
    {
        "entity": "value.strength",
        "key":    "V1",
        "value":  "The Stronger I am, the More Humble I am, the More I help.",
    },
    {
        "entity": "value.hope",
        "key":    "V2",
        "value":  "Even if it is the worst kind of person, always assign him a value of +1 — because that 1 is hope that he may change.",
    },
    {
        "entity": "value.hope",
        "key":    "V2.classifier.poor_steals",
        "value":  "If a person steals and he is poor = don't blame the person, it's the system.",
    },
    {
        "entity": "value.hope",
        "key":    "V2.classifier.wealthy_steals",
        "value":  "If a person is wealthy and he steals = bad.",
    },
    {
        "entity": "value.hope",
        "key":    "V2.classifier.wealthy_kleptomania",
        "value":  "If a person is wealthy and he steals while having kleptomania = a medical problem.",
    },
]

def build_patch() -> str:
    now = int(time.time())
    lines = []
    for i, v in enumerate(VALUES):
        op = {
            "sql": (
                "INSERT INTO loci_facts (entity,key,value,value_type,embedding,"
                "source_trust,source_session,source_ts,heat,last_access_ts,"
                "version,prev_version_id,superseded_by,tier,created_ts,updated_ts) "
                "VALUES (?,?,?,?,NULL,?,?,?,?,?,1,NULL,NULL,'VALUES',?,?)"
            ),
            "params": [
                v["entity"], v["key"], v["value"], "value",
                1.0,                          # source_trust = user-stated
                "seed_values",                # source_session
                now - (len(VALUES)-i),        # ordering: V1 first, V2 next, then classifiers
                1.0,                          # heat=1 forever per Arko 2026-08-03
                now,
                now, now,
            ],
        }
        lines.append(json.dumps(op, sort_keys=True))
    return "\n".join(lines) + "\n"

def main():
    patch = {"signer": "loci_facts", "target": TARGET_REL, "op": "append", "content": build_patch()}
    # sign
    p = subprocess.run(["python3", str(SIGN)], input=json.dumps(patch), capture_output=True, text=True, check=True)
    # apply through writer
    r = subprocess.run(["python3", str(WRITER)], input=p.stdout, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"[seed_values] writer refused: {r.stderr}")
    # commit to DB
    commit = Path("/Volumes/DevDrive/Memory/extractors/loci_facts_extractor.py")
    r2 = subprocess.run(["python3", str(commit)], capture_output=True, text=True)
    print(r2.stderr, file=sys.stderr)
    print("[seed_values] Values V1 + V2 (+3 classifier facts) seeded as VALUES tier.")

if __name__ == "__main__":
    main()
