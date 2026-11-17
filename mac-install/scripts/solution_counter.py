#!/usr/bin/env python3
"""solution_counter.py — track known-problem solves and refinements.

Storage: /Volumes/DevDrive/Memory-state/solution_counter.json  (writable)

CLI:
  python3 solution_counter.py --lookup "problem description"
  python3 solution_counter.py --record --problem "..." --tokens 1240 --time-ms 380 \
                              --improvement "used cached CARD retrieval instead of full API"
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, sys, time, unicodedata
from pathlib import Path

STATE = Path("/Volumes/DevDrive/Memory-state")
FILE  = STATE / "solution_counter.json"

def _normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    s = re.sub(r"[^a-z0-9\s]", " ", s.lower())
    return " ".join(s.split())

def phash(problem: str) -> str:
    return hashlib.sha256(_normalize(problem).encode()).hexdigest()[:24]

def load() -> dict:
    if not FILE.exists(): return {}
    try: return json.loads(FILE.read_text())
    except Exception: return {}

def save(d: dict):
    STATE.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, sort_keys=True, indent=2))
    os.replace(tmp, FILE)

def lookup(problem: str) -> dict:
    h = phash(problem)
    d = load().get(h, {})
    if not d:
        return {"problem_hash": h, "solve_count": 0}
    return {"problem_hash": h, **d}

def record(problem: str, tokens: int, time_ms: int, improvement: str | None):
    d = load()
    h = phash(problem)
    r = d.get(h) or {
        "problem_hint": problem[:120],
        "solve_count": 0,
        "avg_tokens_used": 0,
        "avg_time_ms": 0,
        "refinement_log": [],
    }
    n = r["solve_count"]
    r["solve_count"] = n + 1
    # running avg
    r["avg_tokens_used"] = int((r["avg_tokens_used"] * n + tokens) / (n + 1))
    r["avg_time_ms"]     = int((r["avg_time_ms"]     * n + time_ms) / (n + 1))
    r["last_solved_ts"]  = int(time.time())
    if improvement:
        r["refinement_log"].append({"ts": int(time.time()), "improvement": improvement})
        r["refinement_log"] = r["refinement_log"][-20:]   # keep last 20
    d[h] = r
    save(d)
    return r

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lookup",  type=str)
    ap.add_argument("--record",  action="store_true")
    ap.add_argument("--problem", type=str)
    ap.add_argument("--tokens",  type=int, default=0)
    ap.add_argument("--time-ms", type=int, default=0)
    ap.add_argument("--improvement", type=str, default=None)
    a = ap.parse_args()

    if a.lookup:
        print(json.dumps(lookup(a.lookup), indent=2)); return
    if a.record:
        if not a.problem: sys.exit("--record needs --problem")
        r = record(a.problem, a.tokens, a.time_ms, a.improvement)
        print(json.dumps({"problem_hash": phash(a.problem), **r}, indent=2)); return
    ap.print_help()

if __name__ == "__main__":
    main()
