#!/usr/bin/env python3
"""
session_scanner.py — orchestrator.

Runs the three extractors in order:
    isymprev → qsymprev → loci_facts
(qsymprev writes the stream that loci_facts consumes; isymprev is independent.)

Idempotent — each extractor tracks its own last-seen mtime per session file.
Safe to run on a cron/launchd interval (e.g. every 30 min).
"""
from __future__ import annotations
import subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

def run(name: str) -> None:
    p = HERE / name
    print(f"=== {name} ===", file=sys.stderr)
    r = subprocess.run(["python3", str(p)])
    if r.returncode:
        sys.exit(f"[scanner] {name} exited {r.returncode}")

if __name__ == "__main__":
    run("isymprev_extractor.py")
    run("qsymprev_extractor.py")
    run("loci_facts_extractor.py")
    print("=== scanner done ===", file=sys.stderr)
