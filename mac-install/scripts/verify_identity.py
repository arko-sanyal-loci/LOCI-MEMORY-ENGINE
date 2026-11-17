#!/usr/bin/env python3
"""verify_identity.py — sudo-only. Challenge Arko with a random N-of-M subset
of the identity factors. Exit 0 on pass, non-zero on fail. Rate-limited.

Called automatically by gated scripts (values_admin, strategy_activator, etc.).
Also runnable directly:
  sudo python3 verify_identity.py --level destructive
  sudo python3 verify_identity.py --level unethical
"""
from __future__ import annotations
import argparse, getpass, hashlib, json, os, random, sys, time, unicodedata
from pathlib import Path

CONFIG_DIR = Path.home() / ".config" / "loci"
ID_PATH    = CONFIG_DIR / "identity.json"
BACKOFF    = CONFIG_DIR / "identity.backoff"
LOCKOUT_MAX  = 3
LOCKOUT_SECS = 15 * 60

def require_sudo():
    if os.geteuid() != 0:
        sys.exit("[verify_identity] must run under sudo")

def normalize(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii")
    return s.strip().lower()

def load_identity() -> dict:
    if not ID_PATH.exists():
        sys.exit(f"[verify_identity] no identity set. Run: sudo python3 set_identity.py")
    return json.loads(ID_PATH.read_text())

def check_lockout():
    if not BACKOFF.exists(): return
    try: st = json.loads(BACKOFF.read_text())
    except: return
    now = int(time.time())
    if st.get("lockout_until", 0) > now:
        sys.exit(f"[verify_identity] locked out for {st['lockout_until']-now}s")

def record_result(ok: bool):
    st = {"failures": 0, "lockout_until": 0}
    if BACKOFF.exists():
        try: st = json.loads(BACKOFF.read_text())
        except: pass
    if ok:
        st = {"failures": 0, "lockout_until": 0}
    else:
        st["failures"] = st.get("failures", 0) + 1
        if st["failures"] >= LOCKOUT_MAX:
            st["lockout_until"] = int(time.time()) + LOCKOUT_SECS
    BACKOFF.write_text(json.dumps(st))
    os.chmod(BACKOFF, 0o600)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--level", choices=("destructive", "extreme", "unethical"), required=True)
    args = ap.parse_args()

    require_sudo()
    check_lockout()

    ident = load_identity()
    factors = ident["factors"]
    thresholds = ident.get("thresholds", {"destructive": 4, "extreme": 5, "unethical": 6})
    required = thresholds[args.level]
    n = min(len(factors), max(required, 3 if args.level != "unethical" else len(factors)))
    # for unethical, ask ALL factors; else ask required + 1 or all if smaller
    if args.level == "unethical":
        subset = list(factors)
    else:
        subset = random.sample(factors, k=n)

    print(f"[verify_identity] level={args.level}, need {required}/{len(subset)} correct", file=sys.stderr)
    correct = 0
    for f in subset:
        a = getpass.getpass(f'  {f["prompt"]}: ')
        a = normalize(a)
        salt = bytes.fromhex(f["salt"])
        if hashlib.sha256(salt + a.encode()).hexdigest() == f["hash"]:
            correct += 1

    ok = correct >= required
    record_result(ok)
    if ok:
        print(f"[verify_identity] PASS ({correct}/{len(subset)})", file=sys.stderr)
        sys.exit(0)
    print(f"[verify_identity] FAIL ({correct}/{len(subset)}, needed {required})", file=sys.stderr)
    sys.exit(1)

if __name__ == "__main__":
    main()
