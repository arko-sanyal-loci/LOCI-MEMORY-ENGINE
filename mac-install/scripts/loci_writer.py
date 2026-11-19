#!/usr/bin/env python3
"""
loci_writer.py — the ONLY thing allowed to mutate /Volumes/DevDrive/Memory.

Reads a signed patch on stdin (or --patch <file>). Verifies HMAC-SHA256
against ~/.config/loci/signing.key. On success:
  1. chflags nouchg on the target file
  2. applies the op (append | replace | create)
  3. chflags uchg back on the target
  4. appends a signed line to the audit log

Any unsigned or bad-signature write attempt is refused and logged.

Patch schema (JSON, one per invocation):
{
  "signer":  "isymprev" | "qsymprev" | "loci_facts",  # who is asking
  "target":  "Memory/streams/isymprev.jsonl",         # relative to DevDrive
  "op":      "append" | "replace" | "create",
  "content": "...",
  "hmac_sha256": "<hex>"                              # over signer|target|op|sha256(content)
}
"""
from __future__ import annotations
import argparse, hashlib, hmac, json, os, subprocess, sys, time
from pathlib import Path

DEVDRIVE = Path(os.environ.get("LOCI_DEVDRIVE", "/Volumes/DevDrive"))
MEMORY   = DEVDRIVE / "Memory"
STATE    = DEVDRIVE / "Memory-state"
AUDIT    = STATE / "audit.jsonl"
KEY_PATH = Path.home() / ".config" / "loci" / "signing.key"
ALLOWED_SIGNERS = {"isymprev", "qsymprev", "loci_facts"}
# Content patterns that indicate the patch tries to write VALUES tier — REFUSED here.
# The only legitimate path for VALUES is scripts/values_admin.py under sudo.
VALUES_TIER_MARKERS = ("'VALUES'", '"VALUES"', "tier='VALUES'", 'tier="VALUES"')


def load_key() -> bytes:
    if not KEY_PATH.exists():
        sys.exit(f"[loci_writer] missing signing key at {KEY_PATH} — run install.sh first")
    st = KEY_PATH.stat()
    if st.st_mode & 0o077:
        sys.exit(f"[loci_writer] {KEY_PATH} has loose perms ({oct(st.st_mode)}); expected 400")
    return KEY_PATH.read_bytes().strip()


def canonical(signer: str, target: str, op: str, content: str) -> bytes:
    h = hashlib.sha256(content.encode()).hexdigest()
    return f"{signer}|{target}|{op}|{h}".encode()


def audit(record: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    record["ts"] = int(time.time())
    with AUDIT.open("a") as f:
        f.write(json.dumps(record, sort_keys=True) + "\n")


def unlock(p: Path) -> None:
    subprocess.run(["chflags", "nouchg", str(p)], check=False)


def lock(p: Path) -> None:
    subprocess.run(["chflags", "uchg", str(p)], check=False)


def apply_patch(patch: dict) -> None:
    # Quarantine check — if integrity_monitor detected injection, refuse ALL writes until cleared
    quar = Path("/Volumes/DevDrive/Memory-state/integrity/quarantine.flag")
    if quar.exists():
        audit({"event": "reject", "reason": "quarantine_active", "signer": patch.get("signer","?")})
        sys.exit("[loci_writer] refused: integrity quarantine active — clear with integrity_monitor.py --clear-quarantine after review")

    key = load_key()
    signer = patch["signer"]
    if signer not in ALLOWED_SIGNERS:
        audit({"event": "reject", "reason": "bad_signer", "signer": signer})
        sys.exit(f"[loci_writer] refused: signer '{signer}' not allowed")

    target_rel = patch["target"]
    if not target_rel.startswith("Memory/"):
        audit({"event": "reject", "reason": "escape", "target": target_rel})
        sys.exit(f"[loci_writer] refused: target must be under Memory/")

    target = DEVDRIVE / target_rel
    op = patch["op"]
    content = patch["content"]

    # HMAC verify
    expected = hmac.new(key, canonical(signer, target_rel, op, content), hashlib.sha256).hexdigest()
    provided = patch.get("hmac_sha256", "")
    if not hmac.compare_digest(expected, provided):
        audit({"event": "reject", "reason": "bad_hmac", "signer": signer, "target": target_rel})
        sys.exit("[loci_writer] refused: HMAC mismatch")

    # VALUES tier is off-limits to the HMAC path — only values_admin.py (sudo) can write.
    if any(marker in content for marker in VALUES_TIER_MARKERS):
        audit({"event": "reject", "reason": "values_tier_forbidden", "signer": signer, "target": target_rel})
        sys.exit("[loci_writer] refused: VALUES tier requires values_admin.py (sudo)")

    # Deception scan — per V5 (Honor). Every content write passes through.
    try:
        import subprocess as _sp
        _scan = _sp.run(
            ["python3", str(Path(__file__).resolve().parent / "deception_scan.py"), "--stdin"],
            input=content, capture_output=True, text=True, timeout=10,
        )
        if _scan.returncode == 2:
            audit({"event": "reject", "reason": "deception_scan_hit", "signer": signer, "target": target_rel})
            sys.exit(f"[loci_writer] refused: deception scan hit — {_scan.stdout[:400]}")
    except FileNotFoundError:
        pass

    # Perform the write
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        unlock(target)
    try:
        if op == "append":
            with target.open("a") as f:
                f.write(content)
        elif op == "replace":
            target.write_text(content)
        elif op == "create":
            if target.exists():
                sys.exit(f"[loci_writer] refused: create but {target} exists")
            target.write_text(content)
        else:
            sys.exit(f"[loci_writer] refused: unknown op '{op}'")
    finally:
        if target.exists():
            lock(target)

    audit({
        "event": "apply",
        "signer": signer,
        "target": target_rel,
        "op": op,
        "content_sha256": hashlib.sha256(content.encode()).hexdigest(),
        "bytes": len(content),
    })


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--patch", type=Path, help="path to signed patch JSON (default: stdin)")
    args = ap.parse_args()
    raw = args.patch.read_text() if args.patch else sys.stdin.read()
    patch = json.loads(raw)
    apply_patch(patch)


if __name__ == "__main__":
    main()
