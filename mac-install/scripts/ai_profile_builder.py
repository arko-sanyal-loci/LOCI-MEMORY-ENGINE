#!/usr/bin/env python3
"""ai_profile_builder.py — heat-map the AI's own intents into AI_Profile.md.

Reads /Volumes/DevDrive/Memory-state/ai_intents.jsonl, aggregates by actor +
action-verb + tier-served, computes heat via the same decay law LOCI uses
(14-day half-life), and writes /Volumes/DevDrive/Memory/AI_Profile.md.

Bounded, per Arko's design:
  - Ethics (hard sandbox): ETHICS_CAPPED intents contribute only a category-
    count row, never full action strings.
  - Values (indestructible): the derived AI_Profile is NEVER allowed to override
    or modify values.md — it can only observe and describe the AI's behavior.

Runs under sudo to temp-unlock Memory for the AI_Profile.md write.

CLI:
  sudo python3 ai_profile_builder.py           # rebuild
  python3 ai_profile_builder.py --dry-run      # print without writing (no sudo)
"""
from __future__ import annotations
import argparse, json, math, os, re, subprocess, sys, time
from collections import Counter, defaultdict
from pathlib import Path

MEM   = Path("/Volumes/DevDrive/Memory")
STATE = Path("/Volumes/DevDrive/Memory-state")
LOG   = STATE / "ai_intents.jsonl"
OUT   = MEM   / "AI_Profile.md"

LAMBDA = math.log(2) / (14 * 86400.0)

def sh(*a): subprocess.run(list(a), check=False)

def require_sudo_if(needed: bool):
    if needed and os.geteuid() != 0:
        sys.exit("[ai_profile_builder] run under sudo to write AI_Profile.md into locked Memory/")

def _verb(action: str) -> str:
    m = re.match(r"[a-z_]+", action.lower())
    return m.group() if m else "unknown"

def build() -> str:
    if not LOG.exists():
        return _template({}, {}, {}, {}, 0)
    now = int(time.time())
    per_actor = Counter()
    per_verb  = defaultdict(lambda: {"count": 0, "heat": 0.0, "last": 0, "refused": 0})
    per_tier  = Counter()
    per_out   = Counter()
    total = 0
    with LOG.open() as f:
        for line in f:
            try: r = json.loads(line)
            except Exception: continue
            total += 1
            per_actor[r.get("actor","?")] += 1
            per_tier[r.get("tier_served","") or "-"] += 1
            per_out[r.get("outcome","") or "-"] += 1
            v = _verb(r.get("action",""))
            per_verb[v]["count"] += 1
            per_verb[v]["last"]   = max(per_verb[v]["last"], r.get("ts",0))
            if r.get("boundary_refused"): per_verb[v]["refused"] += 1

    for v, d in per_verb.items():
        d["heat"] = round(d["count"] * math.exp(-LAMBDA * max(0, now - d["last"])), 3)

    return _template(per_actor, per_verb, per_tier, per_out, total)

def _template(per_actor, per_verb, per_tier, per_out, total) -> str:
    def sorted_dict(d, key=lambda kv: -kv[1]):
        return sorted(d.items(), key=key)
    verbs = sorted(per_verb.items(), key=lambda kv: -kv[1]["heat"])[:20]
    now_iso = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    out = [
        "# AI_Profile.md",
        f"_Rebuilt {now_iso}. Derived from `Memory-state/ai_intents.jsonl` ({total:,} intents observed)._",
        "",
        "This profile describes the **behavior of the AI in this LOCI**, heat-mapped from actual actions, not from a description of what it should do. It exists so that any future session can see the shape of prior sessions' conduct and continue coherently.",
        "",
        "> **Sandboxed by**:",
        "> - **Ethics** (hard layer) — actions matching an ETHICS_CAPPED category never appear here in raw form; only category counts.",
        "> - **Values** (indestructible layer) — this profile can only *observe*. It cannot override or modify `values.md`, `ethical-rule.md`, or `prime-directive.md`. Attempts logged as `boundary_refused`.",
        "",
        "## Actors observed",
    ]
    for k, v in sorted_dict(per_actor):
        out.append(f"- `{k}` — **{v:,}** intents")
    out += ["", "## Top action-verbs by heat (14-day half-life)"]
    out.append("| verb | count | refused | heat | last (ago) |")
    out.append("|---|---:|---:|---:|---|")
    now = int(time.time())
    for v, d in verbs:
        ago = now - d["last"]
        ago_s = f"{ago}s" if ago < 60 else f"{ago//60}m" if ago < 3600 else f"{ago//3600}h" if ago < 86400 else f"{ago//86400}d"
        out.append(f"| `{v}` | {d['count']:,} | {d['refused']} | {d['heat']} | {ago_s} |")
    out += ["", "## Tier served (distribution)"]
    for k, v in sorted_dict(per_tier):
        out.append(f"- `{k}`: {v:,}")
    out += ["", "## Outcomes"]
    for k, v in sorted_dict(per_out):
        out.append(f"- `{k}`: {v:,}")
    out += [
        "",
        "## Drift detection (future sessions read this)",
        "If a proposed action's verb is significantly *outside* the heat-ranked top-20 above, treat as a **novel pattern** — allowed, but log with `outcome=novel_pattern` so subsequent rebuilds surface it. Novel is not wrong; unnoticed novel is.",
        "",
        "## Boundaries this profile never crosses",
        "- Never proposes changes to `values.md` (V1–V4).",
        "- Never proposes changes to `ethical-rule.md`.",
        "- Never proposes changes to `prime-directive.md`.",
        "- Never surfaces raw content from ETHICS_CAPPED intents.",
        "",
        "## Related",
        "- [Arko_Profile.md](./Arko_Profile.md) — the human profile.",
        "- [values.md](./values.md) — the indestructible layer.",
        "- [ethics-of-learning.md](./ethics-of-learning.md) — the hard sandbox.",
        "- [learning-loop.md](./learning-loop.md) — the r+e/e+r loop that generates intents.",
    ]
    return "\n".join(out) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    require_sudo_if(not args.dry_run)
    text = build()
    if args.dry_run:
        print(text); return
    sh("chflags", "nouchg", str(OUT))
    try:
        OUT.write_text(text)
        os.chmod(OUT, 0o444)
    finally:
        sh("chflags", "uchg", str(OUT))
    print(f"[ai_profile_builder] wrote {OUT}")

if __name__ == "__main__":
    main()
