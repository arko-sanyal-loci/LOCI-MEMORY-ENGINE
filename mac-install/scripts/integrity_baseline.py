#!/usr/bin/env python3
"""integrity_baseline.py — snapshot SHA-256 of every Memory/ file.

Baselines get stored at /Volumes/DevDrive/Memory-state/integrity/baseline.json
(chmod 400, chflags uchg). Any drift detected by integrity_monitor.py against
this baseline is a suspected injection unless a matching signed-patch event
exists in audit.jsonl.

Refresh the baseline ONLY after intentional patches (patch*.sh). The install
scripts call this at their tail.

CLI:
  sudo python3 integrity_baseline.py --refresh
  python3 integrity_baseline.py --show
"""
from __future__ import annotations
import argparse, hashlib, json, os, subprocess, sys, time
from pathlib import Path

MEM     = Path("/Volumes/DevDrive/Memory")
STATE   = Path("/Volumes/DevDrive/Memory-state")
DIR     = STATE / "integrity"
BASE    = DIR / "baseline.json"

def sh(*a): subprocess.run(list(a), check=False)

def require_sudo():
    if os.geteuid() != 0:
        sys.exit("[integrity_baseline] --refresh needs sudo (writes chmod 400 + chflags uchg)")

def hash_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""): h.update(chunk)
    return h.hexdigest()

def scan() -> dict:
    out = {}
    for p in MEM.rglob("*"):
        if not p.is_file(): continue
        try:
            out[str(p)] = {
                "sha256": hash_file(p),
                "size":   p.stat().st_size,
                "mtime":  int(p.stat().st_mtime),
            }
        except Exception:
            pass
    return out

def refresh():
    require_sudo()
    DIR.mkdir(parents=True, exist_ok=True)
    os.chmod(DIR, 0o700)
    baseline = {
        "generated_ts": int(time.time()),
        "root": str(MEM),
        "count": 0,
        "files": {},
    }
    files = scan()
    baseline["count"] = len(files)
    baseline["files"] = files
    if BASE.exists():
        sh("chflags", "nouchg", str(BASE))
    BASE.write_text(json.dumps(baseline, sort_keys=True, indent=2))
    os.chmod(BASE, 0o400)
    sh("chflags", "uchg", str(BASE))
    print(f"[integrity_baseline] baselined {len(files):,} files → {BASE}")

def show():
    if not BASE.exists():
        sys.exit(f"[integrity_baseline] no baseline yet — run: sudo python3 {Path(__file__).name} --refresh")
    b = json.loads(BASE.read_text())
    print(f"generated_ts : {b['generated_ts']} ({time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(b['generated_ts']))})")
    print(f"root         : {b['root']}")
    print(f"count        : {b['count']:,}")

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--refresh", action="store_true")
    g.add_argument("--show", action="store_true")
    a = ap.parse_args()
    if a.refresh: return refresh()
    if a.show:    return show()

if __name__ == "__main__":
    main()
