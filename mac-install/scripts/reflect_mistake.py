#!/usr/bin/env python3
"""reflect_mistake.py — the "learn from past mistakes" arm of the learning loop.

Per Arko (2026-08-03): "Always use the learning loop especially the reflection
part to create memories of past mistakes allowing you to avoid them."

What this does:
  1. Records the mistake into `solution_counter.json` under a MISTAKE_PATTERN
     hash — so any future call to SC.lookup with a similar description will
     surface it (solve_count > 0 means "seen before, refine, don't re-attempt").
  2. Writes an ARSENAL-tier loci_fact so `loci_query.py` finds it by keyword.
  3. Appends to Memory/mistakes.md (human-readable catalog).
  4. Emits an audit event.

CLI:
  python3 reflect_mistake.py \\
    --category schema_detection \\
    --mistake "sniff_schema only checked line 1 of JSONL — missed prefix metadata" \\
    --cause "assumed Claude Code JSONL starts with content, but starts with 1-2 queue-op lines" \\
    --fix "scan first 40 lines; classify as claude_code if any line has parentUuid" \\
    --file /Volumes/DevDrive/Memory/scripts/transcript_ingest.py

Retrieve later:
  python3 /Volumes/DevDrive/Memory/extractors/loci_query.py --q "schema detection"
  python3 /Volumes/DevDrive/Memory/scripts/solution_counter.py --lookup "sniff schema first line only"
"""
from __future__ import annotations
import argparse, json, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
try:
    import solution_counter as SC
except Exception:
    SC = None

STATE = Path("/Volumes/DevDrive/Memory-state")
AUDIT = STATE / "audit.jsonl"
MEM   = Path("/Volumes/DevDrive/Memory")
CATALOG = MEM / "mistakes.md"

def audit(rec: dict, severity: str = "info"):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time()); rec.setdefault("severity", severity)
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

def arsenal_write(entity: str, key: str, value: str, source: str):
    aw = HERE / "arsenal_writer.py"
    if not aw.exists(): return False, "no_arsenal_writer"
    r = subprocess.run(
        ["python3", str(aw), "--entity", entity, "--key", key,
         "--value", value[:8000], "--source", source],
        capture_output=True, text=True, timeout=30,
    )
    return (r.returncode == 0, (r.stderr or r.stdout)[:200])

def append_catalog(rec: dict) -> tuple[bool, str]:
    """Append to Memory/mistakes.md (bypasses uchg via sudo chflags dance)."""
    entry = (
        f"\n## {rec['ts_iso']}  —  {rec['category']}\n\n"
        f"**Mistake**: {rec['mistake']}\n\n"
        f"**Cause**: {rec['cause']}\n\n"
        f"**Fix**: {rec['fix']}\n\n"
    )
    if rec.get("file"):
        entry += f"**File**: `{rec['file']}`\n\n"
    if rec.get("session_ref"):
        entry += f"**Session ref**: {rec['session_ref']}\n\n"

    header = ("# Mistake catalog — reflections that future sessions read first\n\n"
              "_This file lives at `/Volumes/DevDrive/Memory/mistakes.md`. Every "
              "entry is also in `solution_counter.json` (so SC.lookup surfaces it) "
              "and in `loci_facts` tier=ARSENAL (so `loci_query.py` retrieves it "
              "by keyword). Read before starting work in a domain you've mistaken "
              "before._\n")
    try:
        subprocess.run(["sudo","chflags","nouchg", str(MEM)], check=False)
        subprocess.run(["sudo","chflags","nouchg", str(CATALOG)], check=False)
        existing = CATALOG.read_text() if CATALOG.exists() else header
        CATALOG.write_text(existing + entry)
        subprocess.run(["sudo","chflags","uchg", str(CATALOG)], check=False)
        subprocess.run(["sudo","chflags","uchg", str(MEM)], check=False)
        return True, "ok"
    except Exception as e:
        return False, str(e)[:200]

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--category", required=True,
                    help="short slug, e.g. schema_detection, evidence_over_read, drive_id_confusion")
    ap.add_argument("--mistake",  required=True, help="one-sentence description of what went wrong")
    ap.add_argument("--cause",    required=True, help="one-sentence root cause")
    ap.add_argument("--fix",      required=True, help="one-sentence fix applied (or 'pending')")
    ap.add_argument("--file",     default="",     help="file(s) fixed, optional")
    ap.add_argument("--session-ref", default="",  help="session or ticket ref, optional")
    a = ap.parse_args()

    rec = {
        "ts_iso":   time.strftime("%Y-%m-%d %H:%M:%S"),
        "category": a.category,
        "mistake":  a.mistake,
        "cause":    a.cause,
        "fix":      a.fix,
        "file":     a.file,
        "session_ref": a.session_ref,
    }

    # 1. solution_counter — makes this discoverable via SC.lookup on similar phrasing
    sc_ok = False
    if SC is not None:
        try:
            problem_key = f"MISTAKE_PATTERN[{a.category}]: {a.mistake}"
            SC.record(problem_key, tokens=0, time_ms=0,
                      improvement=f"CAUSE: {a.cause} | FIX: {a.fix}")
            sc_ok = True
        except Exception as e:
            audit({"event":"reflect_mistake.sc_record_err","err":str(e)[:200]}, "warning")

    # 2. arsenal loci_fact
    arsenal_value = (
        f"MISTAKE ({a.category}): {a.mistake}\n"
        f"CAUSE: {a.cause}\n"
        f"FIX: {a.fix}\n"
        f"FILE: {a.file}\n"
        f"REF: {a.session_ref}"
    )
    aw_ok, aw_msg = arsenal_write(
        entity=f"mistake.{a.category}",
        key=f"{int(time.time())}",
        value=arsenal_value,
        source="reflect_mistake",
    )

    # 3. mistakes.md catalog
    cat_ok, cat_msg = append_catalog(rec)

    # 4. audit
    audit({"event": "reflect_mistake.recorded", **rec,
           "sc_ok": sc_ok, "arsenal_ok": aw_ok, "catalog_ok": cat_ok})

    print(json.dumps({
        "status": "recorded" if (sc_ok and aw_ok and cat_ok) else "partial",
        "solution_counter_ok": sc_ok,
        "arsenal_ok": aw_ok, "arsenal_msg": aw_msg,
        "catalog_ok": cat_ok, "catalog_msg": cat_msg,
    }, indent=2))

if __name__ == "__main__":
    main()
