#!/usr/bin/env python3
"""integrity_monitor.py — continuous drift-detector for Memory/.

Re-hashes every Memory/ file, diffs against baseline.json. Any drift is either
(a) an intentional patch — matches a `loci_writer` or `values_admin` or
`patch*` audit entry within a small time window — or (b) INJECTION — no
matching audit → CRITICAL alert + refuse-any-further-writes-until-cleared.

Modes:
  --check        one-shot scan; exit 0=clean, 1=drift-with-audit, 2=INJECTION
  --watch        loop every N seconds
  --refresh      rebaseline after an accepted intentional change (sudo)

Runs unprivileged. Alerts go to Memory-state/audit.jsonl and to macOS notification.
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

MEM   = Path("/Volumes/DevDrive/Memory")
STATE = Path("/Volumes/DevDrive/Memory-state")
BASE  = STATE / "integrity" / "baseline.json"
AUDIT = STATE / "audit.jsonl"
QUAR  = STATE / "integrity" / "quarantine.flag"

INTENTIONAL_EVENTS = {
    "apply", "values_admin.add", "values_admin.update", "values_admin.remove",
    "values_lock_migrated", "patch_applied",
}
DRIFT_WINDOW_S = 60   # a drift is considered intentional only if a matching audit event exists within this window before-or-after the mtime

def sh(*a): return subprocess.run(list(a), capture_output=True, text=True, check=False)

def hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()

def load_baseline() -> dict:
    if not BASE.exists():
        sys.exit(f"[integrity_monitor] no baseline — run: sudo python3 {Path(__file__).parent}/integrity_baseline.py --refresh")
    return json.loads(BASE.read_text())["files"]

def load_audit_events() -> list[dict]:
    if not AUDIT.exists(): return []
    out = []
    for line in AUDIT.read_text().splitlines()[-5000:]:
        try: out.append(json.loads(line))
        except Exception: pass
    return out

def is_intentional(path_str: str, mtime: int, events: list[dict]) -> bool:
    """Does an audit event within DRIFT_WINDOW_S corroborate an intentional change to this path?"""
    for e in events:
        ev = e.get("event", "")
        if not any(ev.endswith(k) or ev == k or ev.startswith(k + ".") for k in INTENTIONAL_EVENTS):
            continue
        if abs(int(e.get("ts", 0)) - mtime) > DRIFT_WINDOW_S:
            continue
        # target hint match
        t = e.get("target") or ""
        if t and (t in path_str or path_str.endswith(t.split("/")[-1])):
            return True
        # or a generic patch event within the window (no target)
        if not t and ev in {"patch_applied", "values_lock_migrated"}:
            return True
    return False

def audit(rec: dict, severity="warning"):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time())
    rec.setdefault("severity", severity)
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

def notify(title: str, body: str):
    # macOS native notification
    subprocess.run([
        "osascript", "-e",
        f'display notification "{body}" with title "{title}" sound name "Basso"'
    ], check=False)

def check() -> int:
    baseline = load_baseline()
    events = load_audit_events()
    now = int(time.time())
    added, removed, changed, injection = [], [], [], []
    seen = set()
    for p in MEM.rglob("*"):
        if not p.is_file(): continue
        s = str(p)
        seen.add(s)
        try:
            cur = hash_file(p)
            mt = int(p.stat().st_mtime)
        except Exception:
            continue
        if s not in baseline:
            (injection if not is_intentional(s, mt, events) else added).append(s)
        elif baseline[s]["sha256"] != cur:
            (injection if not is_intentional(s, mt, events) else changed).append(s)
    for s in baseline:
        if s not in seen:
            removed.append(s)

    total = len(added) + len(removed) + len(changed) + len(injection)
    if injection:
        # QUARANTINE — block further writes until an operator clears
        STATE.mkdir(parents=True, exist_ok=True)
        QUAR.write_text(json.dumps({
            "raised_ts": now, "reason": "unattributed drift",
            "injection_paths": injection,
        }, indent=2))
        os.chmod(QUAR, 0o400)
        audit({"event": "integrity_monitor.INJECTION_ALERT",
               "count": len(injection), "paths": injection[:20]}, severity="critical")
        notify("LOCI INJECTION ALERT",
               f"{len(injection)} file(s) changed with no matching signed-patch audit")
        return 2
    if changed or added or removed:
        audit({"event": "integrity_monitor.drift_ok",
               "added": added, "removed": removed, "changed": changed}, severity="info")
        return 1
    return 0

def watch(interval: float):
    print(f"[integrity_monitor] watching {MEM} every {interval}s — Ctrl+C to exit")
    try:
        while True:
            rc = check()
            marker = ["clean", "drift-attributed", "INJECTION"][rc]
            print(f"  {time.strftime('%H:%M:%S')}  {marker}")
            time.sleep(interval)
    except KeyboardInterrupt:
        print("")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check",   action="store_true")
    g.add_argument("--watch",   action="store_true")
    g.add_argument("--interval", type=float, default=30.0)
    g.add_argument("--refresh", action="store_true", help="alias for integrity_baseline.py --refresh")
    g.add_argument("--clear-quarantine", action="store_true", help="clear the quarantine flag (after review)")
    a = ap.parse_args()
    if a.refresh:
        subprocess.run(["sudo", "python3", str(Path(__file__).with_name("integrity_baseline.py")), "--refresh"])
        return
    if a.clear_quarantine:
        if not QUAR.exists(): print("no quarantine"); return
        if os.geteuid() != 0: sys.exit("clear-quarantine needs sudo")
        os.chmod(QUAR, 0o600); QUAR.unlink()
        audit({"event": "integrity_monitor.quarantine_cleared"}, severity="warning")
        print("quarantine cleared"); return
    if a.check:  sys.exit(check())
    if a.watch:  watch(a.interval)

if __name__ == "__main__":
    main()
