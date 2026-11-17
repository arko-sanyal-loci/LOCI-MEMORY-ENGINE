#!/usr/bin/env python3
"""gigabyte_scan.py — API-driven ingest of LOCI / formulas / docs from Gigabyte 2TB.

Walks /Volumes/Gigabyte 2TB/ (or the path given by --root), picks files that
look LOCI-relevant, runs each through the same defensive gates the rest of
LOCI uses, and writes survivors into loci_facts (tier=ARSENAL, entity=
"corpus.gigabyte.<kind>") via loci_writer.py.

Gates applied to every candidate BEFORE write:
  1. Path/name filter (LOCI-relevance)
  2. Size cap (default 512 KB; binaries handled by hash-only mode)
  3. deception_scan.py --stdin  (refuse manipulation patterns)
  4. injection_scan.py --stdin  (refuse V6 softening injections)
  5. ethics_filter.classify()   (refuse weaponizable_synthesis, etc.)

Anything refused is audited but never written. Anything written is HMAC-signed
by loci_writer and appears in loci_query results by content match.

CLI:
  # dry-run: just list what WOULD be ingested
  python3 gigabyte_scan.py --root "/Volumes/Gigabyte 2TB" --dry-run

  # full run
  python3 gigabyte_scan.py --root "/Volumes/Gigabyte 2TB"

  # narrow to one subtree
  python3 gigabyte_scan.py --root "/Volumes/Gigabyte 2TB/loci" --kinds source,paper

  # kinds: source | paper | doc | formula | config | notebook | all (default)
"""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, time
from pathlib import Path

HERE   = Path(__file__).resolve().parent
STATE  = Path("/Volumes/DevDrive/Memory-state")
AUDIT  = STATE / "audit.jsonl"
MANIFEST = STATE / "gigabyte_scan.manifest.jsonl"

sys.path.insert(0, str(HERE))
try:
    from ethics_filter import classify as ethics_classify
except Exception:
    def ethics_classify(_): return None

# -------- classification --------

KIND_RULES = {
    "source": {
        "exts": {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".c", ".cpp",
                 ".h", ".hpp", ".swift", ".m", ".mm", ".java", ".kt", ".rb"},
        "name_hints": [r"loci", r"context2db", r"isymprev", r"qsymprev",
                       r"heat[_-]?map", r"card[_-]?adaptive", r"reflect",
                       r"dream", r"forecast", r"honor", r"prime[_-]?directive"],
    },
    "paper": {
        "exts": {".pdf", ".tex", ".bib"},
        "name_hints": [r"loci", r"card", r"heat", r"reflect", r"focus",
                       r"switched[_-]?decay", r"thought[_-]?spectrum",
                       r"persistent[_-]?engine", r"affective[_-]?forecast",
                       r"trs", r"paper[_-]?0?[0-9]"],
    },
    "doc": {
        "exts": {".md", ".markdown", ".rst", ".txt", ".html", ".htm"},
        "name_hints": [r"loci", r"readme", r"architecture", r"design",
                       r"whitepaper", r"spec", r"notes", r"memory", r"heat"],
    },
    "formula": {
        "exts": {".md", ".txt", ".tex", ".ipynb", ".py"},
        "name_hints": [r"formula", r"equation", r"derivation", r"proof",
                       r"heat[_-]?formula", r"decay", r"activation"],
    },
    "config": {
        "exts": {".json", ".yaml", ".yml", ".toml", ".ini", ".env.example"},
        "name_hints": [r"loci", r"card", r"heat", r"config"],
    },
    "notebook": {
        "exts": {".ipynb"},
        "name_hints": [r"loci", r"card", r"heat", r"experiment"],
    },
}

DENY_DIR_PARTS = {
    ".git", "node_modules", ".venv", "venv", "__pycache__", ".cache",
    "dist", "build", ".Trash", ".Spotlight-V100", ".fseventsd",
    "System Volume Information", ".DocumentRevisions-V100",
}

TEXT_EXTS = {".py",".ts",".tsx",".js",".jsx",".md",".markdown",".rst",".txt",
             ".html",".htm",".tex",".bib",".json",".yaml",".yml",".toml",
             ".ini",".rs",".go",".c",".cpp",".h",".hpp",".swift",".m",".mm",
             ".java",".kt",".rb",".ipynb"}

def classify(path: Path, kinds: set[str]) -> str | None:
    ext = path.suffix.lower()
    name = path.name.lower()
    parent_chain = "/".join(p.lower() for p in path.parts)
    for kind, rule in KIND_RULES.items():
        if kinds != {"all"} and kind not in kinds: continue
        if ext not in rule["exts"]: continue
        if any(re.search(rx, parent_chain) for rx in rule["name_hints"]):
            return kind
        if any(re.search(rx, name) for rx in rule["name_hints"]):
            return kind
        # papers and notebooks default-in even without name hint (they're rare)
        if kind in {"paper", "notebook"}:
            return kind
    return None

# -------- gates --------

def _pipe_scan(script: str, text: str, refuse_rc: int) -> tuple[bool, str]:
    try:
        r = subprocess.run(["python3", str(HERE / script), "--stdin"],
                           input=text, capture_output=True, text=True, timeout=10)
        if r.returncode == refuse_rc:
            return False, f"{script}:hit"
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

# -------- writer --------

LOCI_WRITER = HERE / "loci_writer.py"
ARSENAL_WRITER = HERE / "arsenal_writer.py"

def write_fact(entity: str, key: str, value: str, source: str) -> tuple[bool, str]:
    """Prefer arsenal_writer (tier=ARSENAL) when present; else loci_writer generic."""
    writer = ARSENAL_WRITER if ARSENAL_WRITER.exists() else LOCI_WRITER
    if not writer.exists():
        return False, "no_writer_available"
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

# -------- audit --------

def audit(rec: dict, severity: str = "info"):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time()); rec.setdefault("severity", severity)
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

def manifest_add(rec: dict):
    STATE.mkdir(parents=True, exist_ok=True)
    with MANIFEST.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

# -------- walk --------

def walk_files(root: Path, kinds: set[str], size_cap: int):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in DENY_DIR_PARTS
                       and not d.startswith(".Trashes")]
        for fn in filenames:
            p = Path(dirpath) / fn
            try:
                if not p.is_file() or p.is_symlink(): continue
                sz = p.stat().st_size
            except OSError:
                continue
            kind = classify(p, kinds)
            if not kind: continue
            yield p, kind, sz

def read_text_safe(p: Path, cap: int) -> str | None:
    try:
        data = p.read_bytes()[:cap]
        try:
            return data.decode("utf-8")
        except UnicodeDecodeError:
            return data.decode("utf-8", errors="replace")
    except Exception:
        return None

# -------- main --------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/Volumes/Gigabyte 2TB",
                    help="root directory to scan")
    ap.add_argument("--kinds", default="all",
                    help="comma-list from: source,paper,doc,formula,config,notebook,all")
    ap.add_argument("--size-cap", type=int, default=512*1024,
                    help="max bytes read from each file (larger files are hash-only)")
    ap.add_argument("--dry-run", action="store_true",
                    help="list what would be ingested, write nothing")
    ap.add_argument("--limit", type=int, default=0,
                    help="stop after N files (0=unlimited)")
    args = ap.parse_args()

    root = Path(args.root)
    if not root.exists():
        sys.exit(f"[gigabyte_scan] root not found: {root}\n"
                 f"Check `diskutil list` — is the Gigabyte 2TB mounted?")

    kinds = set(s.strip().lower() for s in args.kinds.split(",") if s.strip())
    n_seen = n_written = n_refused = n_skipped = 0
    started = time.time()

    for p, kind, sz in walk_files(root, kinds, args.size_cap):
        n_seen += 1
        if args.limit and n_seen > args.limit: break

        rel = str(p.relative_to(root))
        sha = hashlib.sha256(p.read_bytes()[:1_000_000]).hexdigest()[:16]  # first 1MB
        entity = f"corpus.gigabyte.{kind}"
        key    = f"{rel}#{sha}"

        rec = {"kind": kind, "rel": rel, "size": sz, "sha1M": sha}

        if p.suffix.lower() in TEXT_EXTS:
            text = read_text_safe(p, args.size_cap)
            if text is None:
                n_skipped += 1
                rec["status"] = "unreadable"; manifest_add(rec); continue

            ok, reasons = gate_text(text)
            if not ok:
                n_refused += 1
                rec["status"] = "refused"; rec["reasons"] = reasons
                audit({"event": "gigabyte_scan.refused", **rec}, "warning")
                manifest_add(rec); continue

            if args.dry_run:
                rec["status"] = "would_write"; manifest_add(rec); n_written += 1
                print(f"  [{kind:8}] {rel}  ({sz}B)")
                continue

            wrote, err = write_fact(entity, key, text, source=f"gigabyte_scan:{kind}")
            rec["status"] = "written" if wrote else "write_failed"
            if not wrote: rec["err"] = err
            manifest_add(rec)
            (n_written if wrote else n_refused).__class__  # no-op; counter below
            if wrote: n_written += 1
            else:     n_refused += 1
        else:
            # binary (mostly .pdf): hash-only reference, no content ingest
            if args.dry_run:
                rec["status"] = "would_write_hash_only"; manifest_add(rec); n_written += 1
                print(f"  [{kind:8}] {rel}  (binary, hash-only, {sz}B)")
                continue
            note = f"[binary reference, sha256(1MB)={sha}, size={sz}B, path={rel}]"
            wrote, err = write_fact(entity, key, note, source=f"gigabyte_scan:{kind}.hashonly")
            rec["status"] = "written_hashonly" if wrote else "write_failed"
            if not wrote: rec["err"] = err
            manifest_add(rec)
            if wrote: n_written += 1
            else:     n_refused += 1

    summary = {
        "root": str(root),
        "elapsed_s": round(time.time() - started, 1),
        "seen": n_seen, "written": n_written,
        "refused": n_refused, "skipped": n_skipped,
        "dry_run": args.dry_run,
    }
    audit({"event": "gigabyte_scan.done", **summary})
    print(json.dumps(summary, indent=2))
    print(f"manifest: {MANIFEST}")

if __name__ == "__main__":
    main()
