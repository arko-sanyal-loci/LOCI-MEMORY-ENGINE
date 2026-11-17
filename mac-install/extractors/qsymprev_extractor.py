#!/usr/bin/env python3
"""
qsymprev_extractor.py — Quantifiable Stream (papers 01 §6 and 02 §1: VERSIONED qsymprev).

Extracts typed facts (API keys, file paths, dates, versions, numeric values with
units, ticket IDs, IPs) from every session with:
  - source_trust (user_stated=1.0 > assistant_inferred=0.5)
  - source_session + source_ts
  - version chain: if same (entity,key) has a new value at later ts, previous
    record is archived and linked via prev_hash → new record wins.

Emits a SIGNED patch appending JSONL to Memory/streams/qsymprev.jsonl.
"""
from __future__ import annotations
import hashlib, json, re, subprocess, sys, time
from pathlib import Path

HERE       = Path(__file__).resolve().parent
DEVDRIVE   = Path("/Volumes/DevDrive")
MEMORY     = DEVDRIVE / "Memory"
STATE      = DEVDRIVE / "Memory-state"
STATE_FILE = STATE / "qsymprev_last_seen.json"
STORE_FILE = MEMORY / "streams" / "qsymprev.jsonl"   # read-back for version-chain
TRANSCRIPTS = DEVDRIVE / "Transcripts"
TARGET_REL = "Memory/streams/qsymprev.jsonl"
SIGNER     = "qsymprev"

# (entity_prefix, key, regex, value_type)
FACT_RULES = [
    ("api_key.anthropic",  "sk-ant",   re.compile(r"sk-ant-api\d{2}-[A-Za-z0-9_-]{20,140}"), "secret"),
    ("api_key.xai",        "xai-key",  re.compile(r"xai-[A-Za-z0-9]{40,140}"),                "secret"),
    ("api_key.openai_fmt", "sk-key",   re.compile(r"sk-[A-Za-z0-9]{40,140}"),                 "secret"),
    ("api_key.github",     "ghp",      re.compile(r"ghp_[A-Za-z0-9]{30,60}"),                 "secret"),
    ("api_key.aws",        "akia",     re.compile(r"AKIA[A-Z0-9]{16}"),                       "secret"),
    ("path.abs",           "path",     re.compile(r"(/(?:Users|Volumes|Library|Applications|tmp|opt|usr|var|home)/[\w./+\- %]+)"), "string"),
    ("ticket.access_now",  "id",       re.compile(r"#(\d{4,7})"),                             "int"),
    ("date.iso",           "date",     re.compile(r"\b(20\d{2}-[01]\d-[0-3]\d)\b"),           "date"),
    ("port.tcp",           "port",     re.compile(r"\bport\s*:?\s*(\d{2,5})\b", re.I),        "int"),
    ("ip.v4",              "ip",       re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),            "string"),
    ("size.bytes",         "bytes",    re.compile(r"\b(\d+(?:\.\d+)?)\s?(KB|MB|GB|TB)\b"),    "size"),
    ("version.semver",     "semver",   re.compile(r"\b(\d+\.\d+\.\d+(?:-[\w.-]+)?)\b"),       "version"),
    ("commit.git",         "sha",      re.compile(r"\b[0-9a-f]{7,40}\b"),                     "string"),
    ("amount.bdt",         "bdt",      re.compile(r"BDT\s*[\d,]+"),                           "money"),
]

USER_TRUST      = 1.0
ASSISTANT_TRUST = 0.5

def load_last() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

def save_last(d: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(d, sort_keys=True))

def existing_index() -> dict[tuple[str, str], dict]:
    """Read current store; return latest-version per (entity,key)."""
    idx: dict[tuple[str, str], dict] = {}
    if not STORE_FILE.exists():
        return idx
    with STORE_FILE.open() as f:
        for line in f:
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("superseded"):
                continue
            k = (r["entity"], r["key"])
            if k not in idx or r["source_ts"] > idx[k]["source_ts"]:
                idx[k] = r
    return idx

def record_hash(r: dict) -> str:
    return hashlib.sha256(json.dumps({k: r[k] for k in ("entity","key","value","source_ts","version")}, sort_keys=True).encode()).hexdigest()

def extract_text_and_role(d: dict) -> tuple[str, str, int]:
    role = d.get("type", "")
    msg = d.get("message") or {}
    c = msg.get("content")
    text = c if isinstance(c, str) else " ".join(p.get("text","") for p in (c or []) if isinstance(p, dict) and p.get("type") == "text") if isinstance(c, list) else ""
    ts = d.get("timestamp")
    if isinstance(ts, str):
        try:    ts = int(time.mktime(time.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")))
        except: ts = 0
    elif not isinstance(ts, int):
        ts = 0
    return text, role, ts

def scan_session(jsonl: Path):
    sid = next((part for part in jsonl.parts if part.startswith("local_")), "unknown")
    mtime = int(jsonl.stat().st_mtime)
    with jsonl.open() as f:
        for line in f:
            try:
                d = json.loads(line)
            except Exception:
                continue
            text, role, ts = extract_text_and_role(d)
            if not text or role not in ("user", "assistant"):
                continue
            trust = USER_TRUST if role == "user" else ASSISTANT_TRUST
            src_ts = ts or mtime
            for entity, key, rx, vtype in FACT_RULES:
                for m in rx.finditer(text):
                    val = m.group(1) if m.groups() else m.group(0)
                    val = val.strip()
                    if len(val) > 300: continue
                    yield {
                        "entity": entity, "key": key, "value": val, "value_type": vtype,
                        "source_trust": trust, "source_role": role,
                        "source_session": sid, "source_ts": src_ts,
                    }

def main() -> None:
    last = load_last()
    idx = existing_index()
    new_records: list[dict] = []
    supersede_marks: list[dict] = []
    new_seen: dict[str, int] = {}

    for jsonl in TRANSCRIPTS.rglob("*.jsonl") if TRANSCRIPTS.exists() else []:
        if jsonl.name == "audit.jsonl":
            continue
        mt = int(jsonl.stat().st_mtime)
        if last.get(str(jsonl), 0) >= mt:
            continue
        for fact in scan_session(jsonl):
            k = (fact["entity"], fact["key"])
            prev = idx.get(k)
            # Version chain: only supersede if value differs AND newer OR trust is higher
            if prev:
                if prev["value"] == fact["value"]:
                    continue  # duplicate — skip
                if fact["source_ts"] < prev["source_ts"] and fact["source_trust"] <= prev["source_trust"]:
                    continue  # stale; keep existing
                # supersede
                supersede_marks.append({"supersede": prev["hash"]})
                new_ver = prev["version"] + 1
                prev_hash = prev["hash"]
            else:
                new_ver, prev_hash = 1, None
            rec = {**fact, "version": new_ver, "prev_hash": prev_hash, "created_ts": int(time.time())}
            rec["hash"] = record_hash(rec)
            new_records.append(rec)
            idx[k] = rec  # in-run dedup
        new_seen[str(jsonl)] = mt

    if not (new_records or supersede_marks):
        print("[qsymprev] no new facts", file=sys.stderr)
        return

    lines = []
    for m in supersede_marks:
        lines.append(json.dumps({"op": "supersede", "hash": m["supersede"], "ts": int(time.time())}, sort_keys=True))
    for r in new_records:
        lines.append(json.dumps(r, sort_keys=True))
    content = "\n".join(lines) + "\n"

    patch = {"signer": SIGNER, "target": TARGET_REL, "op": "append", "content": content}
    sign = HERE.parent / "scripts" / "sign_patch.py"
    p = subprocess.run(["python3", str(sign)], input=json.dumps(patch), capture_output=True, text=True, check=True)
    writer = HERE.parent / "scripts" / "loci_writer.py"
    r = subprocess.run(["python3", str(writer)], input=p.stdout, capture_output=True, text=True)
    if r.returncode:
        sys.exit(f"[qsymprev] writer refused: {r.stderr}")

    last.update(new_seen)
    save_last(last)
    print(f"[qsymprev] {len(new_records)} new facts, {len(supersede_marks)} superseded", file=sys.stderr)

if __name__ == "__main__":
    main()
