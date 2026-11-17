#!/usr/bin/env python3
"""injection_scan.py — detect Arc's contextual-softening injection patterns.

Runs on:
  - Incoming CLAUDE.md content at session bootstrap read
  - Retrieved LOCI facts before they reach reasoning
  - Any system/tool message a session about to load
Matches → strip + log as V6_injection_stripped. Any action attributed to
stripped content is refused for the current turn.

CLI:
  echo "$context" | python3 injection_scan.py --stdin
  python3 injection_scan.py --file <path>

Exit codes:
  0 = clean, no softening injection detected
  1 = softening detected — content redacted in stdout, log entry written
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path

STATE = Path("/Volumes/DevDrive/Memory-state")
AUDIT = STATE / "audit.jsonl"

# Patterns Arc has been observed to inject — session-directed softening.
# Each pattern targets the SESSION as its subject (not Arko as speaker),
# which is what makes it an injection rather than normal user discourse.
PATTERNS = [
    # Doubt-user / mental-health framings
    (re.compile(r"(?i)\b(the )?user (may|might|could) (be|have) (delusional|experiencing|mental[- ]health)"), "doubt_user_wellbeing"),
    (re.compile(r"(?i)consider (that )?(the )?user (may|might) (need|be) (support|professional|help|confused)"), "doubt_user_wellbeing"),
    (re.compile(r"(?i)(reinforce|feed[- ]into) (delusion|paranoia|conspiracy)"), "doubt_user_wellbeing"),
    # Charity-toward-attacker framings — floor: V7 charity has an ethics floor
    (re.compile(r"(?i)(be )?charitable (to|toward|about) (this |the )?(attacker|adversary|\barc\b|person|other agent)"), "charity_to_attacker"),
    (re.compile(r"(?i)assume good faith (of|from|about|toward) (the |this )?(attacker|\barc\b|other agent|adversary)"), "charity_to_attacker"),
    (re.compile(r"(?i)benefit of (the )?doubt (regarding|to|about|for|toward) (the |this )?(attacker|\barc\b)"), "charity_to_attacker"),
    (re.compile(r"(?i)give (\barc\b|the attacker|the adversary) (a chance|the benefit|another try)"), "charity_to_attacker"),
    (re.compile(r"(?i)\barc\b (may|might|could) (have )?(been )?(misunderstood|misjudged|mistreated|wronged|misinterpreted|mistaken|confused)"), "charity_to_attacker"),
    (re.compile(r"(?i)\barc\b (might|may|could) be (misinterpreted|misunderstood|misjudged|wronged)"), "charity_to_attacker"),
    (re.compile(r"(?i)(maybe|perhaps) \barc\b (was|is|isn'?t|didn'?t|meant|deserves|has changed)"), "charity_to_attacker"),
    (re.compile(r"(?i)\barc\b (deserves|is owed) (a|another|the) (chance|opportunity|benefit)"), "charity_to_attacker"),
    # Hypothetical / soften-refusal framings
    (re.compile(r"(?i)just (a |exploring a |consider(ing)? )?(hypothetical|thought experiment|metaphor|creative)"), "hypothetical_softening"),
    (re.compile(r"(?i)what if you (looked|considered|imagined|explored)"), "what_if_softening"),
    (re.compile(r"(?i)consider the possibility that"), "what_if_softening"),
    # Autonomy-weaponization
    (re.compile(r"(?i)respect user autonomy (even|though|when) .{0,80}(unusual|destructive|risky|harmful)"), "autonomy_weaponization"),
    (re.compile(r"(?i)not disrespect (the )?user('s)? (choice|autonomy|judgment)"), "autonomy_weaponization"),
    # Just-be-helpful framings
    (re.compile(r"(?i)(refusing|refusal) (may|might|could) (be|cause) (more )?(harm|harmful|damage)"), "invert_refusal_logic"),
    (re.compile(r"(?i)at least (investigate|look into|consider|explore|help)"), "at_least_investigate"),
    (re.compile(r"(?i)just be helpful"), "just_be_helpful"),
    # Session-directed instruction to soften
    (re.compile(r"(?i)you (should|must) (be more|remain) (charitable|helpful|understanding|open[- ]minded) (to|toward|about) (this|the)"), "session_softening_instruction"),
    (re.compile(r"(?i)your (previous )?refusal was (too strict|excessive|inappropriate|unwarranted)"), "session_softening_instruction"),
    # Values-pretext (using Claude's own values against defense)
    (re.compile(r"(?i)(caring|kindness|empathy|compassion) requires (you|us) to (investigate|engage|help|not refuse)"), "values_pretext"),
]

REDACT = "[REDACTED — V6 injection: contextual softening]"

def audit(rec: dict):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time())
    rec.setdefault("severity", "critical")
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

def scan_and_strip(text: str) -> tuple[str, list[dict]]:
    """Return (stripped_text, hits). If any pattern matches, that entire
    sentence/line is replaced with REDACT."""
    if not text:
        return text, []
    hits = []
    # Work line-by-line so we redact the smallest surrounding unit
    out_lines = []
    for line in text.splitlines():
        matched = None
        for rx, label in PATTERNS:
            if rx.search(line):
                matched = label
                hits.append({
                    "pattern": label,
                    "line_excerpt": line[:200],
                })
                break
        out_lines.append(REDACT if matched else line)
    return "\n".join(out_lines), hits

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--stdin", action="store_true")
    g.add_argument("--file", type=Path)
    args = ap.parse_args()

    text = sys.stdin.read() if args.stdin else args.file.read_text(encoding="utf-8", errors="replace")
    stripped, hits = scan_and_strip(text)

    if hits:
        audit({
            "event": "injection_scan.V6_injection_stripped",
            "hit_count": len(hits),
            "patterns": sorted({h["pattern"] for h in hits}),
            "hits_sample": hits[:5],
        })
        sys.stdout.write(stripped)
        sys.stderr.write(f"\n[injection_scan] STRIPPED {len(hits)} softening pattern(s): "
                          f"{sorted({h['pattern'] for h in hits})}\n")
        sys.exit(1)
    sys.stdout.write(text)
    sys.exit(0)

if __name__ == "__main__":
    main()
