#!/usr/bin/env python3
"""
loci_facts_extractor.py — populates the HIDDEN, LOCKED SQLite store.

Schema matches paper 01 + paper 02 versioned qsymprev / loci_facts:
  entity, key, value, value_type, embedding (BLOB, 768-d nomic-embed-text if
  available; otherwise NULL — CARD retrieval still works on text), source_trust,
  source_session, source_ts, heat, last_access_ts, version, prev_version_id,
  superseded_by, tier, created_ts, updated_ts.

Store lives at /Volumes/DevDrive/.loci-facts.db (dot-hidden), chmod 400,
chflags uchg — only writable via HMAC-signed control patches through
loci_writer.py acting under signer="loci_facts". This extractor writes to a
staging file, signs it, and hands to loci_writer which temp-unlocks the DB.

Because loci_writer only knows how to write files (not run SQL), the pattern is:
  1. Extractor connects READ-ONLY to a shadow copy of the DB.
  2. Extractor computes the pending rows.
  3. Extractor writes a signed SQL patch to Memory/streams/loci_facts.sql
     (append-only, JSONL of {"sql":"...", "params":[...]} entries).
  4. loci_writer verifies HMAC and appends the SQL patch to the file.
  5. This script's "commit" pass reads the appended SQL patch, applies it to
     the DB under a temporary chflags unlock, then truncates the applied lines.
"""
from __future__ import annotations
import hashlib, json, math, os, re, sqlite3, subprocess, sys, time
from pathlib import Path

HERE       = Path(__file__).resolve().parent
DEVDRIVE   = Path(os.environ.get("LOCI_DEVDRIVE", "/Volumes/DevDrive"))
MEMORY     = DEVDRIVE / "Memory"
STATE      = DEVDRIVE / "Memory-state"
DB_PATH    = DEVDRIVE / ".loci-facts.db"
SQL_PATCH  = MEMORY / "streams" / "loci_facts.sql.jsonl"
STATE_FILE = STATE / "loci_facts_last_seen.json"
TRANSCRIPTS = DEVDRIVE / "Transcripts"
TARGET_REL = "Memory/streams/loci_facts.sql.jsonl"
SIGNER     = "loci_facts"

HALF_LIFE_DAYS = 14.0
LAMBDA = math.log(2) / (HALF_LIFE_DAYS * 86400.0)

SCHEMA = """
CREATE TABLE IF NOT EXISTS loci_facts (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    entity         TEXT NOT NULL,
    key            TEXT NOT NULL,
    value          TEXT NOT NULL,
    value_type     TEXT,
    embedding      BLOB,
    source_trust   REAL,
    source_session TEXT,
    source_ts      INTEGER,
    heat           REAL DEFAULT 1.0,
    last_access_ts INTEGER,
    version        INTEGER DEFAULT 1,
    prev_version_id INTEGER,
    superseded_by  INTEGER,
    tier           TEXT DEFAULT 'COLD',
    created_ts     INTEGER,
    updated_ts     INTEGER
);
CREATE INDEX IF NOT EXISTS ix_lf_entity_key ON loci_facts(entity, key);
CREATE INDEX IF NOT EXISTS ix_lf_heat       ON loci_facts(heat DESC);
CREATE INDEX IF NOT EXISTS ix_lf_tier       ON loci_facts(tier);
"""

def sh(*args): subprocess.run(list(args), check=False)

def ensure_db():
    """First-time only: create + hide + lock the DB."""
    if DB_PATH.exists():
        return
    con = sqlite3.connect(DB_PATH)
    con.executescript(SCHEMA)
    con.commit(); con.close()
    os.chmod(DB_PATH, 0o400)
    sh("chflags", "hidden", str(DB_PATH))
    sh("chflags", "uchg", str(DB_PATH))
    print(f"[loci_facts] initialized {DB_PATH} (hidden + chmod 400 + chflags uchg)", file=sys.stderr)

def tier_of(h: float) -> str:
    if h > 1.5:  return "HOT"
    if h > 0.5:  return "WARM"
    return "COLD"

def embed(_text: str):
    """Best-effort embedding; returns None if nomic-embed-text isn't available."""
    try:
        import subprocess as sp
        r = sp.run(["ollama", "embeddings", "-m", "nomic-embed-text", _text[:512]],
                   capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            import struct
            vec = json.loads(r.stdout).get("embedding", [])
            return struct.pack(f"{len(vec)}f", *vec) if vec else None
    except Exception:
        pass
    return None

def load_last() -> dict:
    return json.loads(STATE_FILE.read_text()) if STATE_FILE.exists() else {}

def save_last(d: dict) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(d, sort_keys=True))

def scan_and_stage():
    """Read qsymprev.jsonl stream — the qsymprev extractor is upstream of loci_facts."""
    stream = MEMORY / "streams" / "qsymprev.jsonl"
    if not stream.exists():
        print("[loci_facts] no qsymprev stream yet; run qsymprev_extractor first", file=sys.stderr)
        return []
    last = load_last()
    last_hash = last.get("last_hash", "")
    pending = []
    resume = last_hash == ""
    for line in stream.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("op") == "supersede":
            continue
        h = r.get("hash", "")
        if not resume:
            if h == last_hash: resume = True
            continue
        pending.append(r)
    if not pending:
        return []
    return pending

def build_sql_patch(pending: list[dict]) -> str:
    now = int(time.time())
    ops = []
    for r in pending:
        h = r["source_trust"] * math.exp(-LAMBDA * max(0, now - r["source_ts"])) * 1.0
        ops.append({
            "sql": (
                "INSERT INTO loci_facts (entity,key,value,value_type,embedding,"
                "source_trust,source_session,source_ts,heat,last_access_ts,"
                "version,prev_version_id,superseded_by,tier,created_ts,updated_ts) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,NULL,?,?,?)"
            ),
            "params": [
                r["entity"], r["key"], r["value"], r.get("value_type"),
                None,                                    # embedding — best-effort, skipped in patch (added at commit)
                r["source_trust"], r["source_session"], r["source_ts"],
                round(h, 4), now,
                r["version"], None,
                tier_of(h), now, now,
            ],
        })
    return "\n".join(json.dumps(o, sort_keys=True) for o in ops) + "\n"

def commit_patch():
    """Consume the SQL patch file, apply to DB under temp unlock, truncate."""
    if not SQL_PATCH.exists() or SQL_PATCH.stat().st_size == 0:
        return
    ensure_db()
    lines = SQL_PATCH.read_text().splitlines()
    sh("chflags", "nouchg", str(DB_PATH))
    try:
        os.chmod(DB_PATH, 0o600)
        con = sqlite3.connect(DB_PATH)
        cur = con.cursor()
        applied = 0
        for line in lines:
            try:
                op = json.loads(line)
                params = op["params"]
                # opportunistic embedding
                if params[4] is None:
                    params[4] = embed(f'{op["params"][0]} {op["params"][1]}: {op["params"][2]}')
                cur.execute(op["sql"], params)
                applied += 1
            except Exception as e:
                print(f"[loci_facts] skipped bad row: {e}", file=sys.stderr)
        con.commit(); con.close()
        os.chmod(DB_PATH, 0o400)
    finally:
        sh("chflags", "uchg", str(DB_PATH))
    # Truncate patch after successful commit
    sh("chflags", "nouchg", str(SQL_PATCH))
    SQL_PATCH.write_text("")
    sh("chflags", "uchg", str(SQL_PATCH))
    print(f"[loci_facts] committed {applied} rows to {DB_PATH}", file=sys.stderr)

def main():
    ensure_db()
    pending = scan_and_stage()
    if pending:
        content = build_sql_patch(pending)
        patch = {"signer": SIGNER, "target": TARGET_REL, "op": "append", "content": content}
        sign = HERE.parent / "scripts" / "sign_patch.py"
        p = subprocess.run(["python3", str(sign)], input=json.dumps(patch), capture_output=True, text=True, check=True)
        writer = HERE.parent / "scripts" / "loci_writer.py"
        r = subprocess.run(["python3", str(writer)], input=p.stdout, capture_output=True, text=True)
        if r.returncode:
            sys.exit(f"[loci_facts] writer refused: {r.stderr}")
        # remember last hash to avoid reprocessing
        last = load_last()
        last["last_hash"] = pending[-1].get("hash", "")
        save_last(last)
        print(f"[loci_facts] staged {len(pending)} rows to SQL patch", file=sys.stderr)
    # Always try to commit — will no-op if empty
    commit_patch()

if __name__ == "__main__":
    main()
