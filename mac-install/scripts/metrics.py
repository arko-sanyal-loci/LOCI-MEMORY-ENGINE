#!/usr/bin/env python3
"""metrics.py — real-time counters for LOCI: token savings + MRR proxy.

State file: /Volumes/DevDrive/Memory-state/metrics.json  (writable, atomic writes)

Recorded per query:
    queries               : total loci_query.py invocations
    tokens_saved_est      : sum of  facts_returned × TOKENS_PER_FACT_EST
    tokens_used_actual    : sum of  actual API tokens spent (0 for local retrieval)
    mrr_proxy_sum         : sum of  1/(rank of first fact that survived z-gate + 1)
    mrr_proxy_n           : count of queries with at least one fact
    hit_rate              : mrr_proxy_n / queries
    per_intent            : counts per CARD intent (PRECISE/SYNTH/UPDATE/TEMPORAL)
    last_query_ts, last_updated_ts

CLI:
    metrics.py --show                  # one-shot print
    metrics.py --watch [--interval 2]  # live refresh
    metrics.py --reset                 # zero all counters (sudo required)
    metrics.py --record ...            # internal — used by loci_query.py
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

STATE_DIR = Path("/Volumes/DevDrive/Memory-state")
METRICS   = STATE_DIR / "metrics.json"

# Conservative estimate: each fact retrieved from LOCI is worth ~250 API-context tokens
# (typical value+entity+key+source_ts = ~250 tokens when hydrated from an API round-trip)
TOKENS_PER_FACT_EST = 250

DEFAULT = {
    "queries": 0,
    "tokens_saved_est": 0,
    "tokens_used_actual": 0,
    "mrr_proxy_sum": 0.0,
    "mrr_proxy_n": 0,
    "per_intent": {"PRECISE": 0, "SYNTH": 0, "UPDATE": 0, "TEMPORAL": 0},
    "last_query_ts": 0,
    "last_updated_ts": 0,
}

def load() -> dict:
    if not METRICS.exists(): return dict(DEFAULT)
    try:
        d = json.loads(METRICS.read_text())
        # migrate: fill any missing keys
        for k, v in DEFAULT.items():
            if k not in d: d[k] = v
        return d
    except Exception:
        return dict(DEFAULT)

def save(d: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = METRICS.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(d, sort_keys=True))
    os.replace(tmp, METRICS)

def record(returned_count: int, intent: str, mrr_rank: int | None, tokens_actual: int = 0):
    """returned_count = # facts returned; mrr_rank = 1-indexed rank of first above-z-gate fact (None if 0)."""
    d = load()
    now = int(time.time())
    d["queries"] += 1
    d["tokens_saved_est"] += returned_count * TOKENS_PER_FACT_EST
    d["tokens_used_actual"] += tokens_actual
    if intent in d["per_intent"]:
        d["per_intent"][intent] += 1
    if mrr_rank is not None and mrr_rank > 0:
        d["mrr_proxy_sum"] += 1.0 / mrr_rank
        d["mrr_proxy_n"] += 1
    d["last_query_ts"] = now
    d["last_updated_ts"] = now
    save(d)

def show(d: dict = None):
    d = d or load()
    hit_rate = d["mrr_proxy_n"] / d["queries"] if d["queries"] else 0.0
    mrr_avg  = d["mrr_proxy_sum"] / d["mrr_proxy_n"] if d["mrr_proxy_n"] else 0.0
    saved_k  = d["tokens_saved_est"] / 1000.0
    saved_m  = saved_k / 1000.0
    ago = int(time.time()) - d["last_query_ts"] if d["last_query_ts"] else -1
    ago_s = f"{ago}s ago" if ago >= 0 else "—"
    print("┌─ LOCI metrics ─────────────────────────────────────────────────")
    print(f"│  queries              : {d['queries']:>10,}")
    print(f"│  tokens_saved_est     : {d['tokens_saved_est']:>10,}  ({saved_k:>8,.1f} K  |  {saved_m:>7,.3f} M)")
    print(f"│  tokens_used_actual   : {d['tokens_used_actual']:>10,}")
    print(f"│  net_savings          : {d['tokens_saved_est'] - d['tokens_used_actual']:>10,}")
    print(f"│  mrr_proxy (avg)      : {mrr_avg:>10.4f}   (n={d['mrr_proxy_n']})")
    print(f"│  hit_rate             : {hit_rate:>10.4f}   (queries with any above-z-gate fact / total)")
    print(f"│  per intent           : {d['per_intent']}")
    print(f"│  last query           : {ago_s}")
    print("└────────────────────────────────────────────────────────────────")

def watch(interval: float):
    try:
        while True:
            os.system("clear" if os.name == "posix" else "cls")
            show()
            print(f"\n(refreshing every {interval}s — Ctrl+C to exit)")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("")

def reset():
    if os.geteuid() != 0:
        sys.exit("[metrics] --reset requires sudo")
    save(dict(DEFAULT))
    print("[metrics] reset to zero")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--show",   action="store_true")
    ap.add_argument("--watch",  action="store_true")
    ap.add_argument("--interval", type=float, default=2.0)
    ap.add_argument("--reset",  action="store_true")
    ap.add_argument("--record", action="store_true", help="internal: --returned N --intent X --mrr-rank K")
    ap.add_argument("--returned", type=int, default=0)
    ap.add_argument("--intent",   type=str, default="PRECISE")
    ap.add_argument("--mrr-rank", type=int, default=None)
    ap.add_argument("--tokens-actual", type=int, default=0)
    a = ap.parse_args()
    if a.reset:  return reset()
    if a.record: return record(a.returned, a.intent, a.mrr_rank, a.tokens_actual)
    if a.watch:  return watch(a.interval)
    return show()

if __name__ == "__main__":
    main()
