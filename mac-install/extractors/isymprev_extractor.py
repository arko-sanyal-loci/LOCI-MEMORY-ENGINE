#!/usr/bin/env python3
"""
isymprev_extractor.py — Informational Stream (paper 01).

Walks Transcripts/, extracts named entities from user + assistant messages,
computes heat = mentions * exp(-λt), 14-day half-life.

Emits a SIGNED patch that appends new entity records (JSONL) to
Memory/streams/isymprev.jsonl, then pipes it to loci_writer.py.
"""
from __future__ import annotations
import json, math, os, re, subprocess, sys, time
from collections import defaultdict
from pathlib import Path

HERE       = Path(__file__).resolve().parent
DEVDRIVE   = Path("/Volumes/DevDrive")
MEMORY     = DEVDRIVE / "Memory"
STATE      = DEVDRIVE / "Memory-state"
STATE_FILE = STATE / "isymprev_last_seen.json"
TRANSCRIPTS = DEVDRIVE / "Transcripts"
TARGET_REL = "Memory/streams/isymprev.jsonl"
SIGNER     = "isymprev"

HALF_LIFE_DAYS = 14.0
LAMBDA         = math.log(2) / (HALF_LIFE_DAYS * 86400.0)

# Entity patterns — tuned for Arko's sessions
PATTERNS = {
    "path":     re.compile(r"(/(?:Users|Volumes|Library|Applications|tmp|opt|usr|var|home)/[\w./+\- %]+)"),
    "url":      re.compile(r"https?://[^\s)>\"']+"),
    "email":    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "session":  re.compile(r"local_[0-9a-f-]{36}"),
    "ticket":   re.compile(r"#\d{4,7}"),
    "project":  re.compile(r"\b(LOCI|CARD|TRS|LOCI\s?∞|multi-defender|billo[- ]?gate|billo[- ]?pc|billo[- ]?vps|Evolution\s?Vapes|Bybit|Access\s?Now|Roza|Arc|Bitdefender|ViewBridge(?:Auxiliary)?)\b", re.I),
    "person":   re.compile(r"\b(Arko(?:\s+Sanyal)?|Roza|Anthropic|Access\s?Now|Bitdefender)\b"),
}

def load_last() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

def save_last(d: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(d, sort_keys=True))

def extract_text(d: dict) -> str:
    msg = d.get("message") or {}
    c = msg.get("content")
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return " ".join(p.get("text", "") for p in c if isinstance(p, dict) and p.get("type") == "text")
    return ""

def walk_sessions() -> list[tuple[Path, str]]:
    """(jsonl_path, session_id)"""
    out = []
    if not TRANSCRIPTS.exists():
        return out
    for p in TRANSCRIPTS.rglob("*.jsonl"):
        # skip audit.jsonl — extractor payload is in projects/*.jsonl
        if p.name == "audit.jsonl":
            continue
        sid = "unknown"
        for part in p.parts:
            if part.startswith("local_"):
                sid = part
                break
        out.append((p, sid))
    return out

def extract_entities(jsonl: Path) -> tuple[dict, int]:
    """Return {(type, name): {count, last_ts}}, and the file mtime as int."""
    counts: dict[tuple[str, str], dict] = defaultdict(lambda: {"count": 0, "last_ts": 0})
    with jsonl.open() as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            text = extract_text(d)
            if not text:
                continue
            ts = d.get("timestamp") or int(jsonl.stat().st_mtime)
            if isinstance(ts, str):
                try:    ts = int(time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")))
                except: ts = int(jsonl.stat().st_mtime)
            for etype, rx in PATTERNS.items():
                for m in rx.finditer(text):
                    name = m.group(0).strip()
                    if len(name) > 200 or len(name) < 2:
                        continue
                    k = (etype, name)
                    counts[k]["count"] += 1
                    counts[k]["last_ts"] = max(counts[k]["last_ts"], int(ts))
    return counts, int(jsonl.stat().st_mtime)

def heat(count: int, last_ts: int, now: int) -> float:
    dt = max(0, now - last_ts)
    return count * math.exp(-LAMBDA * dt)

def tier(h: float) -> str:
    if h > 1.5:  return "HOT"
    if h > 0.5:  return "WARM"
    return "COLD"

def build_records() -> list[dict]:
    now = int(time.time())
    last_seen = load_last()
    all_entities: dict[tuple[str, str], dict] = defaultdict(lambda: {"count": 0, "last_ts": 0, "sessions": set()})
    new_seen: dict[str, int] = {}

    for jsonl, sid in walk_sessions():
        mtime = int(jsonl.stat().st_mtime)
        key = str(jsonl)
        if last_seen.get(key, 0) >= mtime:
            continue
        counts, m = extract_entities(jsonl)
        for k, v in counts.items():
            all_entities[k]["count"]   += v["count"]
            all_entities[k]["last_ts"]  = max(all_entities[k]["last_ts"], v["last_ts"])
            all_entities[k]["sessions"].add(sid)
        new_seen[key] = m

    if not new_seen:
        return []

    records = []
    for (etype, name), v in all_entities.items():
        h = heat(v["count"], v["last_ts"], now)
        records.append({
            "type":      etype,
            "name":      name,
            "count":     v["count"],
            "last_ts":   v["last_ts"],
            "heat":      round(h, 4),
            "tier":      tier(h),
            "sessions":  sorted(v["sessions"]),
            "extracted_ts": now,
        })
    records.sort(key=lambda r: -r["heat"])

    # persist state — do this AFTER we've built the patch (so a failed apply retries)
    last_seen.update(new_seen)
    save_last(last_seen)
    return records

def main() -> None:
    records = build_records()
    if not records:
        print("[isymprev] no new sessions since last run", file=sys.stderr)
        return
    content = "".join(json.dumps(r, sort_keys=True) + "\n" for r in records)
    patch = {"signer": SIGNER, "target": TARGET_REL, "op": "append", "content": content}
    # sign
    sign = HERE.parent / "scripts" / "sign_patch.py"
    p = subprocess.run(["python3", str(sign)], input=json.dumps(patch), capture_output=True, text=True, check=True)
    signed = p.stdout
    # apply
    writer = HERE.parent / "scripts" / "loci_writer.py"
    r = subprocess.run(["python3", str(writer)], input=signed, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"[isymprev] writer refused: {r.stderr}")
    print(f"[isymprev] appended {len(records)} entities to {TARGET_REL}", file=sys.stderr)

if __name__ == "__main__":
    main()
