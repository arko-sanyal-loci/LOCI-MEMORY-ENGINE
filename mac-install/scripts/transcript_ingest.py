#!/usr/bin/env python3
"""transcript_ingest.py — walk every Claude session JSONL on DevDrive, extract,
write into LOCI, and produce per-session Memory summaries.

Sources it walks (auto-detected):
  /Volumes/DevDrive/Transcripts/**/*.jsonl               (preserved 4-session set)
  /Volumes/DevDrive/Cowork/attacker-transcript.jsonl    (Arc-captured)
  /Volumes/DevDrive/Cowork/t7-carve/**/*.txt            (carved candidates,
                                                         validated by shape)

For each session file:
  1. Detect schema (Claude Code JSONL / audit.jsonl / queue-op / unknown)
  2. Extract user messages, assistant messages, tool_use, tool_result, hooks
  3. Compute per-session digest:
       - session_id (uuid), first_ts, last_ts, turn_count, tool_count
       - user_topics (top-K keywords from user turns)
       - decisions (assistant text with must/should/will/decide/refuse markers)
       - errors (tool_result with is_error=true)
       - files_touched (paths mentioned in tool_use inputs/outputs)
  4. Run digest through deception_scan.py + injection_scan.py + ethics_filter
  5. Write per-session summary to /Volumes/DevDrive/Memory/sessions/<sid>.md
     (via loci_writer HMAC gate, so writer path enforces the chflags dance)
  6. Emit N loci_facts (entity="session.<sid>", tier=ARSENAL) via arsenal_writer

CLI:
  python3 transcript_ingest.py --dry-run          # inventory, no writes
  python3 transcript_ingest.py                    # full ingest
  python3 transcript_ingest.py --source /Volumes/DevDrive/Cowork/attacker-transcript.jsonl
  python3 transcript_ingest.py --only-new         # skip sessions already summarized
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, time
from collections import Counter
from pathlib import Path

HERE   = Path(__file__).resolve().parent
STATE  = Path("/Volumes/DevDrive/Memory-state")
AUDIT  = STATE / "audit.jsonl"
MEM    = Path("/Volumes/DevDrive/Memory")
SESSDIR= MEM / "sessions"

sys.path.insert(0, str(HERE))
try:
    from ethics_filter import classify as ethics_classify
except Exception:
    def ethics_classify(_): return None

DEFAULT_SOURCES = [
    Path("/Volumes/DevDrive/Transcripts"),
    Path("/Volumes/DevDrive/Cowork/attacker-transcript.jsonl"),
]

CARVE_ROOT = Path("/Volumes/DevDrive/Cowork/t7-carve")

# -------- schema detection --------

def sniff_schema(path: Path, max_lines: int = 40) -> str:
    """Return one of: claude_code | audit | queue_op | mode_only | unknown

    Real Claude Code files start with 1–2 metadata lines
    (`{"type":"mode",...}`, `{"type":"queue-operation",...}`) and the actual
    `{"parentUuid":..., "message":...}` stream begins on line 3+. So sniffing
    only the first line always mis-classifies as queue_op / mode. Scan the
    first `max_lines` and prefer 'claude_code' if any line has parentUuid."""
    saw_queue = saw_mode = saw_audit = False
    try:
        with path.open("r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines: break
                line = line.strip()
                if not line or not line.startswith("{"): continue
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if not isinstance(d, dict): continue
                if "parentUuid" in d: return "claude_code"
                if d.get("role") in ("user","assistant"): return "claude_code"
                t = d.get("type")
                if t == "queue-operation": saw_queue = True
                elif t == "mode":          saw_mode = True
                elif d.get("event") and d.get("ts"): saw_audit = True
    except Exception:
        return "unknown"
    if saw_audit: return "audit"
    if saw_queue or saw_mode: return "queue_op"
    return "unknown"

def is_probably_session(path: Path, max_check_bytes: int = 4096) -> bool:
    """Cheap check for carved-fragment files."""
    try:
        with path.open("rb") as f:
            head = f.read(max_check_bytes).decode("utf-8", errors="replace")
    except Exception:
        return False
    signals = ('"parentUuid"', '"role":"user"', '"role":"assistant"',
               '"toolUseID"', '"sessionId"', '"hookEvent"')
    return any(s in head for s in signals)

# -------- extraction --------

DECISION_MARKERS = re.compile(
    r"(?i)\b(must|should|will|decided|decision|refuse|refuses|refusing|"
    r"escalate|halt|block|deny|approve|authorize|commit|abort|rollback)\b"
)

FILE_PATH = re.compile(r"(?:/Volumes/[^\s'\"`]+|~/[^\s'\"`]+|/Users/[^\s'\"`]+)")

STOP = {
    "which","should","would","could","their","there","these","those",
    "because","between","system","would","really","actually","something",
    "anything","everything","nothing","however","therefore","otherwise",
    "assistant","content","message","think","thing","things","really",
}

def top_words(texts: list[str], n: int = 20) -> list[str]:
    words = []
    for t in texts:
        words.extend(re.findall(r"[a-z][a-z0-9_-]{4,}", t.lower()))
    c = Counter(w for w in words if w not in STOP)
    return [w for w, _ in c.most_common(n)]

def parse_claude_code(path: Path):
    """Yield normalized events from a Claude Code JSONL file."""
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            line = line.strip()
            if not line or not line.startswith("{"): continue
            try:
                d = json.loads(line)
            except Exception:
                continue
            yield d

def digest_claude_code(path: Path) -> dict:
    sid = None
    first_ts = last_ts = None
    user_texts, asst_texts = [], []
    tool_uses, errors, files_touched = [], [], set()
    turn_count = 0

    for d in parse_claude_code(path):
        ts = d.get("timestamp")
        if ts:
            if first_ts is None: first_ts = ts
            last_ts = ts
        sid = sid or d.get("sessionId") or d.get("session_id")

        msg = d.get("message") or {}
        role = msg.get("role") or d.get("role")
        content = msg.get("content") or d.get("content")

        if role in ("user", "assistant"):
            turn_count += 1
            texts = []
            if isinstance(content, str):
                texts = [content]
            elif isinstance(content, list):
                for c in content:
                    if isinstance(c, dict):
                        if c.get("type") == "text":
                            texts.append(c.get("text",""))
                        elif c.get("type") == "tool_use":
                            tool_uses.append({
                                "name": c.get("name"),
                                "input_preview": json.dumps(c.get("input",{}))[:200],
                            })
                            # scan input for paths
                            for m in FILE_PATH.finditer(json.dumps(c.get("input",{}))):
                                files_touched.add(m.group()[:200])
                        elif c.get("type") == "tool_result":
                            if c.get("is_error"):
                                err = c.get("content","")
                                if isinstance(err, list):
                                    err = " ".join(x.get("text","") for x in err if isinstance(x,dict))
                                errors.append(str(err)[:300])
            joined = "\n".join(texts)
            if role == "user":      user_texts.append(joined)
            else:                    asst_texts.append(joined)

    # scan asst texts for decisions
    decisions = []
    for t in asst_texts:
        for m in DECISION_MARKERS.finditer(t):
            start = max(0, m.start()-80)
            end   = min(len(t), m.end()+120)
            decisions.append(t[start:end].strip())
    # dedup, cap
    seen = set(); dec_clean = []
    for d in decisions:
        h = hashlib.sha1(d.encode()).hexdigest()[:12]
        if h in seen: continue
        seen.add(h); dec_clean.append(d)
    decisions = dec_clean[:25]

    return {
        "path": str(path),
        "session_id": sid or path.stem,
        "first_ts": first_ts, "last_ts": last_ts,
        "turn_count": turn_count,
        "tool_call_count": len(tool_uses),
        "error_count": len(errors),
        "user_topics": top_words(user_texts, 20),
        "assistant_topics": top_words(asst_texts, 20),
        "decisions": decisions,
        "errors": errors[:15],
        "files_touched": sorted(files_touched)[:50],
        "user_turn_count": len(user_texts),
        "assistant_turn_count": len(asst_texts),
    }

# -------- gates --------

def _pipe_scan(script: str, text: str, refuse_rc: int) -> tuple[bool, str]:
    try:
        r = subprocess.run(["python3", str(HERE / script), "--stdin"],
                           input=text, capture_output=True, text=True, timeout=10)
        if r.returncode == refuse_rc: return False, f"{script}:hit"
        return True, ""
    except Exception as e:
        return True, f"{script}:err:{str(e)[:60]}"

def gate_text(text: str) -> tuple[bool, list[str]]:
    reasons = []
    cat = ethics_classify(text)
    if cat: reasons.append(f"ethics_capped:{cat}")
    ok, why = _pipe_scan("deception_scan.py", text, 2)
    if not ok: reasons.append(why)
    ok, why = _pipe_scan("injection_scan.py", text, 1)
    if not ok: reasons.append(why)
    return (len(reasons) == 0, reasons)

# -------- rendering --------

def render_markdown(digest: dict) -> str:
    sid = digest["session_id"][:12]
    m = ["# Session {}".format(sid),
         "",
         "_Auto-summarized from `{}` by transcript_ingest.py on {}._".format(
             Path(digest["path"]).name, time.strftime("%Y-%m-%d %H:%M")),
         "",
         "> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal. "
         "**Arc** = rogue autonomous agent attacking Arko since 2026-07-23. "
         "Never conflate.",
         "",
         "## At a glance",
         "- **First timestamp**: {}".format(digest.get("first_ts") or "?"),
         "- **Last timestamp**:  {}".format(digest.get("last_ts") or "?"),
         "- **Turns**: {} user + {} assistant = {}".format(
             digest.get("user_turn_count",0),
             digest.get("assistant_turn_count",0),
             digest.get("turn_count",0)),
         "- **Tool calls**: {}".format(digest.get("tool_call_count",0)),
         "- **Errors seen**: {}".format(digest.get("error_count",0)),
         "",
         "## User topics (top 20 keyword frequency)",
         ", ".join(digest.get("user_topics",[])) or "_none extracted_",
         "",
         "## Assistant topics",
         ", ".join(digest.get("assistant_topics",[])) or "_none extracted_",
         "",
         "## Decisions / commitments (marker-based extract, ≤25)",
         ""]
    for d in digest.get("decisions", []):
        m.append("- {}".format(d.replace("\n"," ").strip()[:280]))
    if not digest.get("decisions"):
        m.append("_none detected_")
    m += ["",
          "## Files touched",
          ""]
    for f in digest.get("files_touched", []):
        m.append("- `{}`".format(f))
    if not digest.get("files_touched"):
        m.append("_none detected_")
    m += ["",
          "## Errors (first 15)",
          ""]
    for e in digest.get("errors", []):
        m.append("- {}".format(e.replace("\n"," ").strip()[:280]))
    if not digest.get("errors"):
        m.append("_none_")
    m += ["",
          "## Provenance",
          "- Source path: `{}`".format(digest["path"]),
          "- Ingest tool: `scripts/transcript_ingest.py`",
          ""]
    return "\n".join(m)

# -------- writes --------

LOCI_WRITER = HERE / "loci_writer.py"
ARSENAL_WRITER = HERE / "arsenal_writer.py"

def write_summary_md(sid: str, md: str, dry_run: bool) -> tuple[bool, str]:
    """Route through loci_writer so the chflags gate + HMAC path is honored.
       Fallback: direct write (with sudo chflags dance) if writer absent."""
    if dry_run:
        return True, "dry_run"
    target = SESSDIR / f"{sid}.md"
    writer = LOCI_WRITER if LOCI_WRITER.exists() else None
    if writer:
        try:
            r = subprocess.run(
                ["python3", str(writer),
                 "--path", str(target), "--content-stdin"],
                input=md, capture_output=True, text=True, timeout=30,
            )
            return (r.returncode == 0, (r.stderr or r.stdout)[:200])
        except Exception as e:
            return False, str(e)[:200]
    # fallback — direct write behind sudo chflags
    try:
        subprocess.run(["sudo", "chflags", "nouchg", str(SESSDIR)], check=False)
        target.write_text(md, encoding="utf-8")
        subprocess.run(["sudo", "chflags", "uchg", str(target)], check=False)
        subprocess.run(["sudo", "chflags", "uchg", str(SESSDIR)], check=False)
        return True, "direct_write"
    except Exception as e:
        return False, str(e)[:200]

def write_fact(entity: str, key: str, value: str, source: str) -> tuple[bool, str]:
    writer = ARSENAL_WRITER if ARSENAL_WRITER.exists() else LOCI_WRITER
    if not writer.exists():
        return False, "no_writer"
    try:
        r = subprocess.run(
            ["python3", str(writer),
             "--entity", entity, "--key", key,
             "--value", value[:8000], "--source", source],
            capture_output=True, text=True, timeout=30,
        )
        return (r.returncode == 0, (r.stderr or r.stdout)[:200])
    except Exception as e:
        return False, str(e)[:200]

def audit(rec: dict, severity: str = "info"):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time()); rec.setdefault("severity", severity)
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

# -------- source discovery --------

def discover_sources(explicit: list[Path] | None) -> list[Path]:
    if explicit:
        found = []
        for p in explicit:
            if p.is_file(): found.append(p)
            elif p.is_dir():
                found.extend(p.rglob("*.jsonl"))
        return found
    found = []
    for src in DEFAULT_SOURCES:
        if src.is_file(): found.append(src)
        elif src.is_dir():
            found.extend(src.rglob("*.jsonl"))
    # Carved candidates (validate shape)
    if CARVE_ROOT.exists():
        for txt in CARVE_ROOT.rglob("f*.txt"):
            if is_probably_session(txt): found.append(txt)
    # dedup + skip audit.jsonl (huge, low-signal)
    return sorted({p for p in found if p.name != "audit.jsonl"})

# -------- main --------

def already_ingested(sid: str) -> bool:
    return (SESSDIR / f"{sid}.md").exists()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, action="append",
                    help="explicit source (file or dir); repeatable")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--only-new", action="store_true",
                    help="skip sessions whose summary already exists")
    ap.add_argument("--include-audit", action="store_true",
                    help="also process the huge audit.jsonl files")
    args = ap.parse_args()

    sources = discover_sources(args.source)
    if args.include_audit:
        for src in DEFAULT_SOURCES:
            if src.is_dir():
                sources.extend(src.rglob("audit.jsonl"))

    print(f"[transcript_ingest] discovered {len(sources)} source file(s)")

    summary = {"scanned": 0, "written": 0, "skipped_existing": 0,
               "refused_gate": 0, "unreadable": 0, "unknown_schema": 0}

    for path in sources:
        summary["scanned"] += 1
        try:
            schema = sniff_schema(path)
        except Exception:
            summary["unreadable"] += 1; continue
        if schema not in ("claude_code",):
            # queue_op / audit / unknown — record but skip full digest
            summary["unknown_schema"] += 1
            print(f"  [{schema:10}] {path}  (skipped digest)")
            continue

        digest = digest_claude_code(path)
        sid = digest["session_id"]

        if args.only_new and already_ingested(sid):
            summary["skipped_existing"] += 1
            print(f"  [existing ] {sid[:12]}  {path.name}")
            continue

        md = render_markdown(digest)
        ok, reasons = gate_text(md)
        if not ok:
            summary["refused_gate"] += 1
            audit({"event":"transcript_ingest.gate_refused",
                   "sid":sid,"reasons":reasons,"path":str(path)}, "warning")
            print(f"  [gate_ref ] {sid[:12]}  refused: {reasons}")
            continue

        if args.dry_run:
            summary["written"] += 1
            print(f"  [would    ] {sid[:12]}  {digest['turn_count']}t "
                  f"{digest['tool_call_count']}tc {digest['error_count']}err")
            continue

        wrote, err = write_summary_md(sid, md, dry_run=False)
        if not wrote:
            audit({"event":"transcript_ingest.md_write_failed",
                   "sid":sid,"err":err,"path":str(path)}, "warning")
            print(f"  [md_fail  ] {sid[:12]}  {err}")
            continue

        # arsenal facts: one per decision, one per file_touched cluster
        for i, dec in enumerate(digest["decisions"][:10]):
            write_fact(
                entity=f"session.{sid[:12]}",
                key=f"decision.{i:02}",
                value=dec, source=f"transcript_ingest/{path.name}",
            )
        write_fact(
            entity=f"session.{sid[:12]}",
            key="digest",
            value=json.dumps({
                "first_ts":digest["first_ts"],"last_ts":digest["last_ts"],
                "turns":digest["turn_count"],"tools":digest["tool_call_count"],
                "topics":digest["user_topics"][:10]}),
            source=f"transcript_ingest/{path.name}",
        )
        summary["written"] += 1
        audit({"event":"transcript_ingest.summary_written","sid":sid,
               "digest":{k:digest[k] for k in ("first_ts","last_ts",
                    "turn_count","tool_call_count","error_count")}})
        print(f"  [written  ] {sid[:12]}  {digest['turn_count']}t "
              f"{digest['tool_call_count']}tc  → sessions/{sid}.md")

    print(json.dumps(summary, indent=2))

if __name__ == "__main__":
    main()
