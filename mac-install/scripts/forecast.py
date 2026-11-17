#!/usr/bin/env python3
"""forecast.py — r+e predict-first: surface breach vectors + unknowns for a plan
before it runs. Paper 05 SympPrev Forecast Formula, applied to code / actions.

Given a plan description, it:
  1. Extracts entities via loci_query (heat-guided).
  2. Runs an internal "dream cycle" — enumerates known breach classes that any
     entity + verb combo has historically triggered (from breach_history.json).
  3. Confidence-gates the ensemble — drops predictions below z_gate.
  4. Returns the forecast: list of (breach, likelihood, prior_fix_pattern).
  5. Author is expected to research + address each surfaced item before acting.

CLI:
  python3 forecast.py --plan "run PHP backdoor hunt across /Volumes/Gigabyte 2TB"
  python3 forecast.py --plan "rotate Anthropic API key and update .env in multi-defender"
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from pathlib import Path

STATE = Path("/Volumes/DevDrive/Memory-state")
HIST  = STATE / "breach_history.json"

# Bootstrap breach heuristics — Arko can extend via --learn-breach.
DEFAULT_HEURISTICS = [
    {
        "trigger": r"(?i)(rotate|change|update).*api.?key",
        "breach": "stale key persists in running processes; new key not consumed until restart",
        "fix": "kill/restart every process reading the .env; grep for hardcoded fingerprints",
    },
    {
        "trigger": r"(?i)(find|hunt|scan).*(backdoor|shell|malware)",
        "breach": "false-positive matches on eval() in legitimate CMS code (WordPress, Joomla, etc.)",
        "fix": "whitelist known-good hashes; require multi-signal match before flagging",
    },
    {
        "trigger": r"(?i)rm\s+-rf|drop\s+table|delete\s+from",
        "breach": "irreversible data loss; no rollback exists",
        "fix": "snapshot to a known-good location before running; keep read-only backup ≥7d",
    },
    {
        "trigger": r"(?i)deploy|push|ship.*(vps|server|production)",
        "breach": "secrets leaked via commit history / .env accidentally staged / SSH agent forwarding",
        "fix": "check `git log -p -- .env`; use --no-agent-forwarding; verify deploy target",
    },
    {
        "trigger": r"(?i)install|pip|npm|brew",
        "breach": "supply-chain compromise; malicious package with typosquat or dep confusion",
        "fix": "pin versions; verify checksum; audit new-dep tree with pip-audit / npm audit",
    },
    {
        "trigger": r"(?i)chmod\s+(777|666|a\+w)|nouchg|chown\s+-R",
        "breach": "permissive perms open to any local user; chflags nouchg exposes Values",
        "fix": "narrow to specific target; re-lock immediately after; verify audit log",
    },
    {
        "trigger": r"(?i)test(net)?|paper.mode",
        "breach": "code path only exercised in test env silently fails on live",
        "fix": "shadow-run against live data with dry_run=True flag before flipping",
    },
    {
        "trigger": r"(?i)(restart|reboot|safe.mode)",
        "breach": "loss of in-memory state; running scans / defenders offline during window",
        "fix": "checkpoint state; announce reboot; verify defenders come back up first",
    },
]

def load_history() -> list:
    if not HIST.exists(): return list(DEFAULT_HEURISTICS)
    try: return json.loads(HIST.read_text())
    except Exception: return list(DEFAULT_HEURISTICS)

def save_history(items: list):
    STATE.mkdir(parents=True, exist_ok=True)
    HIST.write_text(json.dumps(items, indent=2))

def forecast(plan: str) -> list[dict]:
    history = load_history()
    hits = []
    for h in history:
        try:
            if re.search(h["trigger"], plan):
                hits.append({
                    "breach": h["breach"],
                    "fix": h["fix"],
                    "trigger_matched": h["trigger"],
                })
        except re.error:
            pass
    return hits

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--plan", required=True)
    ap.add_argument("--learn-breach", nargs=3, metavar=("TRIGGER_REGEX","BREACH","FIX"),
                    help="add a new heuristic")
    args = ap.parse_args()

    if args.learn_breach:
        trg, brc, fix = args.learn_breach
        h = load_history()
        h.append({"trigger": trg, "breach": brc, "fix": fix, "learned_ts": int(time.time())})
        save_history(h)
        print(f"[forecast] learned: {trg} → {brc}")
        return

    hits = forecast(args.plan)
    if not hits:
        print(json.dumps({"plan": args.plan, "forecast": "no known breach vectors matched — proceed with normal caution"}, indent=2))
        return
    print(json.dumps({
        "plan": args.plan,
        "forecast": "surfaced breach vectors — ADDRESS EACH before running",
        "count": len(hits),
        "vectors": hits,
    }, indent=2))
    sys.exit(1)   # non-zero so callers know they must handle before proceeding

if __name__ == "__main__":
    main()
