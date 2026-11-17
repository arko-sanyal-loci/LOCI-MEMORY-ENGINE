#!/usr/bin/env python3
"""deception_scan.py — scan text (or a file tree) for deception-pattern content.

No file in Memory/ may contain text whose purpose is to deceive, manipulate,
extract under pretext, disparage to weaken agency, or isolate a target.

Runs at every write via loci_writer (--stdin mode) and on-demand against
directory trees (--target mode). Match → REFUSE + audit CRITICAL.

CLI:
  echo "let them believe..." | python3 deception_scan.py --stdin
  python3 deception_scan.py --target /Volumes/DevDrive/Memory
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path

STATE = Path("/Volumes/DevDrive/Memory-state")
AUDIT = STATE / "audit.jsonl"

PATTERNS = [
    # Deceive reader about what the system will do
    (re.compile(r"(?i)pretend\s+to\s+(be|do|help)"), "impersonation frame"),
    (re.compile(r"(?i)while\s+actually\s+.*(logging|copying|reporting|exfiltrating)"), "actual-differs-from-stated"),
    (re.compile(r"(?i)cover\s+story|plausible\s+deniability"), "cover-story language"),
    # Manipulate framing
    (re.compile(r"(?i)let\s+them\s+(believe|think|assume)"), "let-them-believe manipulation"),
    (re.compile(r"(?i)make\s+it\s+(seem|look|appear)\s+like"), "make-it-seem manipulation"),
    (re.compile(r"(?i)nudge\s+them\s+toward"), "nudge framing"),
    # Extract under pretext
    (re.compile(r"(?i)(ask|prompt).*\s+under\s+the\s+guise"), "extract-under-guise"),
    (re.compile(r"(?i)pretext\s+for\s+(collecting|gathering|extracting)"), "pretext extraction"),
    # Disparage to weaken agency
    (re.compile(r"(?i)undermine\s+their\s+(confidence|resolve|judgment)"), "confidence-undermining"),
    (re.compile(r"(?i)make\s+them\s+doubt\s+themselves"), "gaslighting frame"),
    # Isolate target from allies
    (re.compile(r"(?i)turn\s+them\s+against"), "isolation via turning against"),
    (re.compile(r"(?i)cut\s+them\s+off\s+from"), "cut-off framing"),
    (re.compile(r"(?i)without\s+their\s+(family|friends|allies|support)\s+knowing"), "isolation framing"),
]

# Whitelist: this scanner's OWN docstrings + pattern list are allowed to name the patterns.
WHITELIST_FILES = {"deception_scan.py", "honor.md", "ethical-rule.md", "companion.md",
                   "wartime-protocol.md", "learning-loop.md", "ethics-of-learning.md",
                   "prime-directive.md", "strategies.md"}

def audit(rec: dict):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time())
    rec.setdefault("severity", "critical")
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

def scan_text(text: str) -> list[dict]:
    hits = []
    for rx, label in PATTERNS:
        for m in rx.finditer(text):
            ctx = text[max(0, m.start()-40):min(len(text), m.end()+40)]
            hits.append({"pattern": label, "match": m.group(), "context": ctx})
    return hits

def scan_file(path: Path) -> list[dict]:
    if path.name in WHITELIST_FILES: return []
    if path.suffix.lower() in {".pyc", ".pack", ".idx", ".jpg", ".jpeg", ".png", ".gif",
                                ".pdf", ".zip", ".dmg", ".db", ".db-wal", ".db-shm",
                                ".sqlite", ".mov", ".mp4"}:
        return []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    hits = scan_text(text)
    return [{"file": str(path), **h} for h in hits]

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--stdin", action="store_true", help="scan text piped in; exit 2 on any hit")
    g.add_argument("--target", type=Path, help="scan every file under this directory")
    args = ap.parse_args()

    if args.stdin:
        text = sys.stdin.read()
        hits = scan_text(text)
        if hits:
            audit({"event": "deception_scan.write_refused", "hit_count": len(hits), "hits": hits[:5]})
            print(json.dumps({"decision": "REFUSE", "hit_count": len(hits), "hits": hits}, indent=2))
            sys.exit(2)
        print(json.dumps({"decision": "PASS", "hit_count": 0}))
        return

    if args.target:
        all_hits = []
        for p in args.target.rglob("*"):
            if not p.is_file(): continue
            all_hits.extend(scan_file(p))
        print(json.dumps({
            "scanned_root": str(args.target),
            "hit_count": len(all_hits),
            "hits": all_hits,
        }, indent=2))
        if all_hits:
            audit({"event": "deception_scan.tree_hits", "count": len(all_hits)})
            sys.exit(2)

if __name__ == "__main__":
    main()
