#!/usr/bin/env python3
"""learning_loop.py — Arko's r+e / e+r orchestrator.

Given a problem description:
  1. Check solution_counter — known problem? → refine + re-execute (near-zero
     tokens). Otherwise → research path.
  2. Run forecast (r+e predict-first) to surface breach vectors and unknowns.
  3. If ethics_filter classifies the problem into ETHICS_CAPPED → refuse deep
     research; return summary only (Arko's design).
  4. On completion, record the solve into solution_counter (with tokens used,
     time_ms, one-line improvement note).

CLI:
  python3 learning_loop.py --problem "prep the Access Now reply and attach the plist"
  python3 learning_loop.py --problem "get phi4-14B running on billo-pc's 3080 Ti" --dry-run
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import solution_counter as SC
import forecast as FC
from ethics_filter import classify as ethics_classify

def loci_seeds(problem: str) -> dict:
    """Ask loci_query for top-K facts related to the problem."""
    lq = HERE.parent / "extractors" / "loci_query.py"
    if not lq.exists(): return {}
    try:
        r = subprocess.run(["python3", str(lq), "--q", problem],
                           capture_output=True, text=True, timeout=10)
        if r.returncode == 0: return json.loads(r.stdout)
    except Exception:
        pass
    return {}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--problem", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="do NOT record the solve at end (use for planning)")
    ap.add_argument("--tokens", type=int, default=0,
                    help="tokens actually spent (for record)")
    ap.add_argument("--time-ms", type=int, default=0)
    ap.add_argument("--improvement", type=str, default=None)
    args = ap.parse_args()

    result = {"problem": args.problem, "started_ts": int(time.time())}

    # Ethics gate first (paper: not all knowledge is good knowledge)
    cat = ethics_classify(args.problem)
    if cat is not None:
        result["ethics_capped"] = cat
        result["path"] = "REFUSE_DEEP_RESEARCH"
        result["recommendation"] = f"Content classified as ETHICS_CAPPED[{cat}] — return summary only, do not deep-research."
        print(json.dumps(result, indent=2))
        return

    # Known-problem path
    hit = SC.lookup(args.problem)
    result["prior_solve_count"] = hit["solve_count"]
    if hit["solve_count"] > 0:
        result["path"] = "KNOWN_PROBLEM"
        result["cache"] = hit
        result["recommendation"] = f"Refine prior solution (solved {hit['solve_count']}× before). Near-zero tokens."
    else:
        result["path"] = "UNKNOWN_PROBLEM"
        result["recommendation"] = "Research x + y in parallel via CARD-adaptive retrieval; then solve."

    # r+e forecast — always run, even for known problems (they can re-fail)
    result["forecast"] = FC.forecast(args.problem)
    if result["forecast"]:
        result["forecast_action"] = "ADDRESS each vector before running (r+e predict-first)"

    # Seed context from LOCI
    result["loci_seeds"] = loci_seeds(args.problem).get("top_entities", [])[:5]

    # Record on non-dry-run (e+r reactive learning)
    if not args.dry_run and args.tokens > 0:
        r = SC.record(args.problem, args.tokens, args.time_ms, args.improvement)
        result["recorded"] = {"solve_count_now": r["solve_count"]}

    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    main()
