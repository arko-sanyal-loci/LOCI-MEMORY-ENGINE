#!/usr/bin/env python3
"""
set_focus.py — declare / resolve an open FOCUS goal.

Focus is the paper 07 switched-decay channel. While a focus is 'open', the
loci_query retrieval boosts facts related to it and suppresses unrelated
CRITICAL_HEAT + HOT/WARM/COLD facts. VALUES are never suppressed.

Usage:
  # open a focus
  python3 set_focus.py --entity "LOCI" --key "restart_on_billo_pc" \
      --value "Bring LOCI back online on Windows workstation" --target-days 30

  # inspect current focus
  python3 set_focus.py --show

  # resolve current focus with a release-taxonomy mode (paper 07)
  python3 set_focus.py --resolve fulfilled
  python3 set_focus.py --resolve re-clamped
  python3 set_focus.py --resolve relinquished
  python3 set_focus.py --resolve nullified
  python3 set_focus.py --resolve abandoned      # flagged as pathological
"""
from __future__ import annotations
import argparse, json, os, sys, time
from pathlib import Path

STATE_DIR = Path("/Volumes/DevDrive/Memory-state")
FOCUS     = STATE_DIR / "focus.json"
ARCHIVE   = STATE_DIR / "focus.archive.jsonl"

RELEASE_MODES = {"fulfilled", "re-clamped", "relinquished", "nullified", "abandoned"}

def load() -> dict | None:
    if not FOCUS.exists(): return None
    try: return json.loads(FOCUS.read_text())
    except: return None

def save(d: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    FOCUS.write_text(json.dumps(d, indent=2))

def archive(d: dict) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with ARCHIVE.open("a") as f:
        f.write(json.dumps(d, sort_keys=True) + "\n")

def open_focus(args) -> None:
    now = int(time.time())
    d = {
        "state": "open",
        "opened_ts": now,
        "entity": args.entity,
        "key": args.key,
        "value": args.value,
        "target_ts": now + args.target_days * 86400,
        "half_life_seconds": 30 * 86400,   # 30-day hold regime (paper 07)
    }
    save(d)
    print(f"[focus] OPENED {args.entity}/{args.key} — target in {args.target_days} days")
    print(json.dumps(d, indent=2))

def resolve(mode: str) -> None:
    d = load()
    if not d or d.get("state") != "open":
        sys.exit("[focus] no open focus to resolve")
    if mode not in RELEASE_MODES:
        sys.exit(f"[focus] unknown release mode; must be one of {sorted(RELEASE_MODES)}")
    now = int(time.time())
    d["state"] = mode
    d["resolved_ts"] = now
    d["hold_seconds"] = now - d["opened_ts"]
    d["release_regime_seconds"] = 3600   # 1h fast collapse (paper 07)
    if mode == "abandoned":
        d["flag"] = "pathological — release without consolidation (paper 07)"
    archive(d)
    FOCUS.unlink()
    print(f"[focus] RESOLVED as {mode}")
    print(json.dumps(d, indent=2))

def show() -> None:
    d = load()
    if not d: print("[focus] none open"); return
    print(json.dumps(d, indent=2))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--entity")
    ap.add_argument("--key")
    ap.add_argument("--value")
    ap.add_argument("--target-days", type=int, default=30)
    ap.add_argument("--show", action="store_true")
    ap.add_argument("--resolve", choices=sorted(RELEASE_MODES))
    args = ap.parse_args()

    if args.show: return show()
    if args.resolve: return resolve(args.resolve)
    if not (args.entity and args.key and args.value):
        sys.exit("[focus] need --entity, --key, --value to open a focus (or use --show / --resolve)")
    if load() and load().get("state") == "open":
        sys.exit("[focus] one already open — resolve it first (--resolve <mode>)")
    open_focus(args)

if __name__ == "__main__":
    main()
