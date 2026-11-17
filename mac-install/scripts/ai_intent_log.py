#!/usr/bin/env python3
"""ai_intent_log.py — append-only log of AI intents across sessions.

Every meaningful action any AI/session takes gets recorded as an intent record.
The log is the raw material for AI_Profile.md.

Bounded by:
  - Values (indestructible outer layer)  — an intent whose action-string violates
    values (via profile_check hard-refuse patterns) is REFUSED before logging.
  - Ethics (hard sandbox)                — an intent whose action-string matches
    an ETHICS_CAPPED category is downgraded to a summary log line.

Storage: /Volumes/DevDrive/Memory-state/ai_intents.jsonl  (append-only, writable)

Called by every gated script and by loci_query on every retrieval.

CLI:
  python3 ai_intent_log.py --log --actor loci_query --action "retrieval for 'x'" \
      --tier-served HOT --outcome pass
  python3 ai_intent_log.py --tail 20
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE = Path("/Volumes/DevDrive/Memory-state")
LOG   = STATE / "ai_intents.jsonl"

def _boundary_check(action: str) -> tuple[str, str | None]:
    """Return (final_action_text, refusal_reason). Refusal = None means allowed."""
    try:
        sys.path.insert(0, str(HERE))
        from ethics_filter import classify
        cat = classify(action)
        if cat:
            return f"[ETHICS_CAPPED summary: {cat}]", None
    except Exception:
        pass
    # values gate via profile_check
    try:
        import subprocess as _sp
        r = _sp.run(["python3", str(HERE / "profile_check.py"), "--action", action],
                    capture_output=True, text=True, timeout=5)
        if r.returncode == 2:   # hard refuse
            return action, "profile_hard_refuse"
    except Exception:
        pass
    return action, None

def log(actor: str, action: str, tier_served: str = "", outcome: str = "",
        focus_related: bool = False, extra: dict | None = None) -> dict:
    final_action, refusal = _boundary_check(action)
    rec = {
        "ts": int(time.time()),
        "actor": actor,
        "action": final_action,
        "tier_served": tier_served,
        "outcome": outcome if not refusal else f"refused:{refusal}",
        "focus_related": focus_related,
        "boundary_refused": bool(refusal),
    }
    if extra: rec.update({k: v for k, v in extra.items() if k not in rec})
    STATE.mkdir(parents=True, exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec

def tail(n: int):
    if not LOG.exists(): print("[ai_intent_log] no log yet"); return
    lines = LOG.read_text().splitlines()[-n:]
    for line in lines:
        try:
            r = json.loads(line)
            ts = time.strftime("%m-%d %H:%M:%S", time.localtime(r["ts"]))
            marker = "×" if r.get("boundary_refused") else "·"
            print(f"  {ts}  {marker}  {r['actor']:20}  {r.get('outcome',''):15}  {r['action'][:60]}")
        except Exception:
            pass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", action="store_true")
    ap.add_argument("--actor", type=str)
    ap.add_argument("--action", type=str)
    ap.add_argument("--tier-served", type=str, default="")
    ap.add_argument("--outcome", type=str, default="")
    ap.add_argument("--focus-related", action="store_true")
    ap.add_argument("--tail", type=int, default=None)
    a = ap.parse_args()
    if a.tail is not None: return tail(a.tail)
    if a.log:
        if not (a.actor and a.action): sys.exit("--log needs --actor and --action")
        r = log(a.actor, a.action, a.tier_served, a.outcome, a.focus_related)
        print(json.dumps(r, sort_keys=True))
        return
    ap.print_help()

if __name__ == "__main__":
    main()
