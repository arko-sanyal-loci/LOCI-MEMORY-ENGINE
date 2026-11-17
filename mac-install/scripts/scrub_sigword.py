#!/usr/bin/env python3
"""scrub_sigword.py — redact sigword occurrences from a target tree.

The sigword is authentication. It must not exist in plaintext anywhere the
attacker (Arc) could read. This script walks a directory, finds any occurrence
that hashes to the stored sigword hash, and replaces it with a redaction
marker. Files are temp-unlocked (chflags nouchg) if needed, patched, and re-
locked.

Usage:
  sudo python3 scrub_sigword.py --target /Volumes/DevDrive/Memory
  sudo python3 scrub_sigword.py --target /Volumes/DevDrive/Transcripts --relock

Requires sudo (chflags unlock and re-lock).
"""
from __future__ import annotations
import argparse, hashlib, os, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from sigword_utils import scrub_text, ocr_image, sigword_present

TEXT_EXTS  = {".md", ".txt", ".jsonl", ".json", ".yaml", ".yml", ".py", ".sh",
              ".html", ".css", ".log", ".conf", ".ini", ".env", ".sql", ""}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".tiff", ".webp"}
SKIP_EXTS  = {".mov", ".mp4", ".pdf", ".zip", ".dmg", ".db", ".db-wal", ".db-shm",
              ".sqlite", ".pyc", ".pack", ".idx", ".dylib", ".so", ".ttf",
              ".otf", ".woff", ".woff2"}


def require_sudo():
    if os.geteuid() != 0:
        sys.exit("[scrub_sigword] must be run under sudo — need to temp-unlock chflags")


def scrub_file(path: Path, do_images: bool) -> int:
    ext = path.suffix.lower()
    if ext in SKIP_EXTS: return 0
    if ext in IMAGE_EXTS:
        if not do_images: return 0
        # Best-effort: OCR the image, check for sigword; if present, WARN — we don't
        # rewrite images. User must review/delete manually.
        if sigword_present(ocr_image(path)):
            print(f"  ⚠ image contains sigword: {path}   (manual review required — image not rewritten)")
        return 0
    if ext and ext not in TEXT_EXTS and ext not in {""}: return 0
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0
    new = scrub_text(text)
    if new == text: return 0
    redacted = new.count("[REDACTED — sigword per V3]") - text.count("[REDACTED — sigword per V3]")
    subprocess.run(["chflags", "nouchg", str(path)], check=False)
    try:
        mode = path.stat().st_mode & 0o777
        path.write_text(new, encoding="utf-8")
        os.chmod(path, mode)
    finally:
        subprocess.run(["chflags", "uchg", str(path)], check=False)
    return redacted


def walk(target: Path, do_images: bool) -> tuple[int, int]:
    files = 0; total = 0
    for p in target.rglob("*"):
        if not p.is_file(): continue
        n = scrub_file(p, do_images)
        if n:
            print(f"  {p}: {n} redactions")
            files += 1; total += n
    return files, total


def main():
    require_sudo()
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", required=True, type=Path)
    ap.add_argument("--relock", action="store_true",
                    help="re-apply chflags uchg to the whole target after scrub")
    ap.add_argument("--images", action="store_true",
                    help="also OCR image files (needs tesseract) and WARN if sigword found")
    args = ap.parse_args()

    if not args.target.exists():
        sys.exit(f"[scrub_sigword] target does not exist: {args.target}")

    files, total = walk(args.target, args.images)
    print(f"[scrub_sigword] {total} redactions across {files} files under {args.target}")

    if args.relock:
        print(f"[scrub_sigword] re-locking {args.target}")
        subprocess.run(["find", str(args.target), "-type", "f", "-exec", "chflags", "uchg", "{}", ";"], check=False)
        subprocess.run(["find", str(args.target), "-type", "d", "-exec", "chflags", "uchg", "{}", ";"], check=False)


if __name__ == "__main__":
    main()
