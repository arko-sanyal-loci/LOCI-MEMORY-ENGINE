#!/usr/bin/env python3
"""lock_segments.py — encrypt sensitive segments of transcript files with
Fernet(PBKDF2-HMAC-SHA256(sigword, per-segment salt)). Replace the original
text with a marker; store the ciphertext at /Volumes/DevDrive/.locked-segments/.

Usage (all require sudo — chflags):
  # lock every JSONL line under --target whose content matches any --pattern
  sudo python3 lock_segments.py \\
      --target /Volumes/DevDrive/Transcripts/…/local_d09eb68c-…/…/44f5f9e4-…jsonl \\
      --pattern 'Cats name \\(' --pattern 'Wife \\(' --pattern 'My Phone' \\
      --pattern 'My Dogs Name' --pattern 'My Mothers Name' --pattern 'My Fathers Name'

Marker format: [LOCKED SEGMENT: <uuid>]  in the message content field.
Ciphertext:   /Volumes/DevDrive/.locked-segments/<uuid>.enc  (chmod 400, chflags uchg)

Companion: unlock_segment.py <uuid>  → prompts for sigword, prints plaintext.
"""
from __future__ import annotations
import argparse, base64, getpass, hashlib, json, os, re, subprocess, sys, uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from cryptography.fernet import Fernet
except Exception:
    sys.exit("[lock_segments] pip3 install cryptography (or --user)")

VAULT = Path("/Volumes/DevDrive/.locked-segments")
SIG_SALT = Path.home() / ".config" / "loci" / "sigword.salt"
SIG_HASH = Path.home() / ".config" / "loci" / "sigword.hash"
PBKDF2_ITERS = 600_000

def require_sudo():
    if os.geteuid() != 0:
        sys.exit("[lock_segments] run under sudo (need chflags unlock/relock)")

def verify_sigword() -> str:
    if not (SIG_SALT.exists() and SIG_HASH.exists()):
        sys.exit("[lock_segments] no sigword set. Run: sudo python3 set_sigword.py")
    sw = getpass.getpass("sigword: ").strip().lower()
    salt = SIG_SALT.read_bytes()
    if hashlib.sha256(salt + sw.encode()).hexdigest() != SIG_HASH.read_text().strip():
        sys.exit("[lock_segments] wrong sigword")
    return sw

def make_fernet(sw: str, salt: bytes) -> Fernet:
    k = hashlib.pbkdf2_hmac("sha256", sw.encode(), salt, PBKDF2_ITERS, dklen=32)
    return Fernet(base64.urlsafe_b64encode(k))

def ensure_vault():
    VAULT.mkdir(parents=True, exist_ok=True)
    os.chmod(VAULT, 0o700)

def sh(*args): subprocess.run(list(args), check=False)

def lock_line(line: str, sw: str, patterns: list[re.Pattern]) -> tuple[str, list[str]]:
    """If any pattern matches inside the message text, encrypt that entire message
    content and replace with a marker. Returns (new_line, list_of_uuids_created)."""
    try:
        d = json.loads(line)
    except Exception:
        return line, []
    msg = d.get("message") or {}
    c = msg.get("content")
    hit_uuids = []
    def maybe_lock(text: str) -> str | None:
        if not isinstance(text, str) or not text: return None
        if not any(rx.search(text) for rx in patterns): return None
        # encrypt
        seg_salt = os.urandom(16)
        f = make_fernet(sw, seg_salt)
        ct = f.encrypt(text.encode())
        seg_id = str(uuid.uuid4())
        blob = seg_salt + ct
        p = VAULT / f"{seg_id}.enc"
        p.write_bytes(blob)
        os.chmod(p, 0o400)
        sh("chflags", "uchg", str(p))
        hit_uuids.append(seg_id)
        return f"[LOCKED SEGMENT: {seg_id}]"
    if isinstance(c, str):
        rep = maybe_lock(c)
        if rep is not None:
            msg["content"] = rep
    elif isinstance(c, list):
        for i, part in enumerate(c):
            if isinstance(part, dict) and part.get("type") == "text":
                rep = maybe_lock(part.get("text", ""))
                if rep is not None:
                    part["text"] = rep
    if not hit_uuids:
        return line, []
    return json.dumps(d) + "\n", hit_uuids

def main():
    require_sudo()
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, type=Path, help="JSONL file to scan (repeatable)")
    ap.add_argument("--pattern", action="append", required=True, help="regex; if it matches inside a message, that whole message content gets locked")
    args = ap.parse_args()

    patterns = [re.compile(p) for p in args.pattern]
    sw = verify_sigword()
    ensure_vault()

    if not args.target.exists():
        sys.exit(f"[lock_segments] missing: {args.target}")

    sh("chflags", "nouchg", str(args.target))
    try:
        with args.target.open() as f:
            lines = f.readlines()
        new_lines = []
        all_uuids = []
        for line in lines:
            nl, uuids = lock_line(line, sw, patterns)
            new_lines.append(nl)
            all_uuids.extend(uuids)
        if all_uuids:
            args.target.write_text("".join(new_lines))
            print(f"[lock_segments] locked {len(all_uuids)} segments in {args.target}:")
            for u in all_uuids: print(f"  {u}")
        else:
            print(f"[lock_segments] no matches in {args.target}")
    finally:
        sh("chflags", "uchg", str(args.target))

if __name__ == "__main__":
    main()
