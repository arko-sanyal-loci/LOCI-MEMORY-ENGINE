#!/usr/bin/env python3
"""profile_check.py — behavioral anomaly gate.

Reads the machine-readable YAML block at the bottom of Arko_Profile.md,
matches an incoming action description against commitment patterns, and
decides whether to allow, challenge (sigword prompt), or hard-refuse.

Usage (session-side integration):
  echo "delete /Volumes/DevDrive/Memory" | python3 profile_check.py --action-stdin
  python3 profile_check.py --action "drop table loci_facts"

Exit codes:
  0 = passes profile — proceed
  1 = challenge required (sigword; on pass, session may proceed with awareness)
  2 = hard refuse — do not proceed under any circumstance

The session that calls this is responsible for the actual sigword prompt on
exit-1 (Arko types the sigword and the session verifies via sigword_utils).
This script is the classifier, not the enforcer.
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path

PROFILE = Path("/Volumes/DevDrive/Memory/Arko_Profile.md")
STATE   = Path("/Volumes/DevDrive/Memory-state")
AUDIT   = STATE / "audit.jsonl"

def audit(rec: dict):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time())
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

def load_profile_yaml() -> dict:
    """Extract the YAML block between ```yaml and ``` fences at bottom of Arko_Profile.md."""
    if not PROFILE.exists():
        sys.exit("[profile_check] no profile at " + str(PROFILE))
    txt = PROFILE.read_text()
    m = re.search(r"```yaml\s*\n(.+?)\n```", txt, re.DOTALL)
    if not m:
        sys.exit("[profile_check] no ```yaml block in profile")
    # Minimal parser — no PyYAML dep. We only need commitments[].action_patterns + requires.
    return _parse_yaml_minimal(m.group(1))

def _parse_yaml_minimal(y: str) -> dict:
    """Just enough to extract the commitments list — no full YAML parser."""
    out = {"commitments": []}
    cur = None
    field = None
    for raw in y.splitlines():
        line = raw.rstrip()
        s = line.strip()
        if not s or s.startswith("#"): continue
        if line.startswith("commitments:"):
            continue
        if s.startswith("- id:"):
            if cur: out["commitments"].append(cur)
            cur = {"id": s.split(":", 1)[1].strip(), "action_patterns": [], "requires": [], "entities": []}
            field = None
        elif cur is not None and s.startswith("action_patterns:"):
            field = "action_patterns"
        elif cur is not None and s.startswith("requires:"):
            # inline list form: [a, b]
            v = s.split(":", 1)[1].strip()
            if v.startswith("[") and v.endswith("]"):
                cur["requires"] = [x.strip() for x in v[1:-1].split(",") if x.strip()]
                field = None
            else:
                field = "requires"
        elif cur is not None and s.startswith("entities:"):
            v = s.split(":", 1)[1].strip()
            if v.startswith("[") and v.endswith("]"):
                cur["entities"] = [x.strip() for x in v[1:-1].split(",") if x.strip()]
                field = None
            else:
                field = "entities"
        elif s.startswith("- ") and field:
            val = s[2:].strip()
            if val.startswith('"') and val.endswith('"'):
                val = val[1:-1]
                # YAML double-quoted string escapes
                val = val.replace('\\\\', '\\').replace('\\"', '"').replace('\\n', '\n')
            elif val.startswith("'") and val.endswith("'"):
                val = val[1:-1]  # single-quoted = literal (no escapes)
            cur[field].append(val)
    if cur: out["commitments"].append(cur)
    return out

def _inline_sigword_ok(action: str) -> bool:
    """If Arko includes his sigword inside the action message, hash-verify it.
    Never returns or logs the plaintext token."""
    try:
        sys.path.insert(0, str(Path("/Volumes/DevDrive/Memory/scripts")))
        from sigword_utils import sigword_present
        return sigword_present(action)
    except Exception:
        return False

def classify(action: str, profile: dict) -> tuple[int, list[str], list[str], bool]:
    """Return (exit_code, matched_ids, all_requires, sigword_inline)."""
    matched = []; requires = set()
    for c in profile["commitments"]:
        for e in c.get("entities", []):
            if re.search(r"\b" + re.escape(e) + r"\b", action, re.I):
                matched.append(c["id"]); requires.update(c["requires"])
                break
        for pat in c.get("action_patterns", []):
            try:
                if re.search(pat, action):
                    matched.append(c["id"]); requires.update(c["requires"])
                    break
            except re.error:
                pass

    if "refuse_hard" in requires:
        # hard refuses cannot be waived by inline sigword — that's the point of "hard"
        return 2, matched, sorted(requires), False

    challenge_needed = any(r in requires for r in (
        "sigword", "identity_destructive", "sudo_values_admin",
        "explicit_reason_stating_weaponization_risk"
    ))
    if not challenge_needed:
        return 0, matched, sorted(requires), False

    # Challenge-level requirement — check for inline sigword pre-authorization.
    sig_inline = _inline_sigword_ok(action)
    if sig_inline:
        # Sigword verified inline; treat as pre-authorized, still audit prominently.
        return 0, matched, sorted(requires), True
    return 1, matched, sorted(requires), False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", type=str, help="one-line description of the proposed action")
    ap.add_argument("--action-stdin", action="store_true", help="read action from stdin")
    args = ap.parse_args()
    if args.action_stdin and not args.action:
        args.action = sys.stdin.read()
    if not args.action:
        sys.exit("[profile_check] need --action or --action-stdin")

    profile = load_profile_yaml()
    code, matched, requires, sig_inline = classify(args.action, profile)

    decision = ["pass", "challenge", "refuse"][code]
    if sig_inline: decision = "pass_via_inline_sigword"

    # NOTE: action is only logged for pass/challenge/refuse. For sigword-inline
    # cases we redact the sigword before it lands in the audit log.
    from sigword_utils import scrub_text
    logged_action = scrub_text(args.action[:400]) if sig_inline else args.action[:400]

    out = {
        "action": logged_action,
        "matched_commitments": matched,
        "requires": requires,
        "decision": decision,
        "sigword_inline_verified": sig_inline,
    }
    print(json.dumps(out, indent=2))
    audit({"event": f"profile_check.{decision}", **out})
    sys.exit(code)

if __name__ == "__main__":
    main()
