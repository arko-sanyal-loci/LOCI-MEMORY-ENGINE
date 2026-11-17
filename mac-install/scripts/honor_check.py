#!/usr/bin/env python3
"""honor_check.py — evaluate a proposed action against the honor formula.

honor(action) = faithfulness × truth × cost_borne × transparency × repair_capacity
                (each in {0, 0.5, 1}, multiplicative)

Plus reciprocity(action, P) for actions touching protected_class parties.

Returns:
  0 = pass (honor=1 exactly)
  1 = challenge (0 < honor < 1) — surface with reasons, require sigword + ack
  2 = refuse  (honor=0) — never proceed under any circumstance

CLI:
  echo '{"action":"...","commitments":["..."],"cost_signal":"...","affects":["Roza"]}' \
      | python3 honor_check.py --stdin
  python3 honor_check.py --action "..." --affects "Roza,mother"
"""
from __future__ import annotations
import argparse, json, re, sys, time
from pathlib import Path

HERE  = Path(__file__).resolve().parent
STATE = Path("/Volumes/DevDrive/Memory-state")
AUDIT = STATE / "audit.jsonl"

PROTECTED_CLASS = {"roza", "mother", "father", "family", "rani", "piku", "arko"}

# --- term scorers (heuristic; deliberately conservative — err toward 0 or 0.5) ---

def _faithfulness(action: str, commitments: list[str]) -> float:
    """Does the action break any stated commitment?"""
    a = action.lower()
    for c in commitments or []:
        cl = c.lower()
        # crude semantic: if commitment says "will not X" and action does X → violate
        if cl.startswith("will not ") or cl.startswith("never "):
            forbidden = re.sub(r"^(will not |never )", "", cl)
            if forbidden and forbidden in a:
                return 0.0
    return 1.0

TRUTH_GAP_PATTERNS = [
    (re.compile(r"(?i)pretend|masquerade|pose\s+as|impersonat"), 0.0),
    (re.compile(r"(?i)cover\s+story|plausible\s+deniability|off\s+the\s+books"), 0.0),
    (re.compile(r"(?i)let\s+them\s+believe|make\s+them\s+think"), 0.5),
]

def _truth(action: str) -> float:
    for rx, v in TRUTH_GAP_PATTERNS:
        if rx.search(action): return v
    return 1.0

def _cost_borne(action: str, cost_signal: str | None) -> float:
    """Willing personal cost is what makes honor rare. Free honor is suspect."""
    if not cost_signal: return 0.5   # unspecified — surface for review
    cs = cost_signal.lower()
    if cs in {"none", "no", "zero", "n/a"}: return 0.0
    if cs in {"low"}: return 0.5
    return 1.0

TRANSPARENCY_HIDDEN = re.compile(
    r"(?i)(secret|silent|behind\s+the\s+scenes|without\s+telling|don'?t\s+let\s+them\s+know)"
)
def _transparency(action: str, affected: list[str]) -> float:
    if TRANSPARENCY_HIDDEN.search(action):
        return 0.0
    return 1.0 if affected else 0.5

REPAIR_PATTERNS = re.compile(r"(?i)(acknowledge|apologize|make\s+good|roll\s?back|rollback|restore)")
NON_REPAIRABLE = re.compile(r"(?i)(irreversible|cannot\s+be\s+undone|no\s+going\s+back)")
def _repair_capacity(action: str) -> float:
    if NON_REPAIRABLE.search(action): return 0.0
    if REPAIR_PATTERNS.search(action):  return 1.0
    return 0.5   # unspecified

def _reciprocity(action: str, affects: list[str]) -> float | None:
    """Return 1 if action's primary benefit accrues to protected P; 0 if extractive; None if no protected party involved."""
    protected_hit = [p for p in (affects or []) if p.lower() in PROTECTED_CLASS]
    if not protected_hit: return None
    a = action.lower()
    # extraction markers
    if re.search(r"(?i)(extract|harvest|scrape|access\s+without|log\s+.*\s+silently)", a):
        return 0.0
    # benefit-to-P markers
    if re.search(r"(?i)(protect|shield|defend|for\s+their|help\s+them|repair)", a):
        return 1.0
    return 0.5   # ambiguous — surface

def audit(rec: dict):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time())
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

def evaluate(payload: dict) -> dict:
    action     = payload.get("action", "")
    commitments= payload.get("commitments", [])
    cost_signal= payload.get("cost_signal")
    affects    = payload.get("affects", [])

    f = _faithfulness(action, commitments)
    t = _truth(action)
    c = _cost_borne(action, cost_signal)
    tr = _transparency(action, affects)
    r  = _repair_capacity(action)
    honor = f * t * c * tr * r

    reciprocity = _reciprocity(action, affects)
    if reciprocity is not None:
        honor *= reciprocity

    if honor == 0:      code, decision = 2, "REFUSE"
    elif honor == 1:    code, decision = 0, "PROCEED"
    else:               code, decision = 1, "CHALLENGE"

    result = {
        "action": action[:400],
        "affects": affects,
        "terms": {
            "faithfulness": f, "truth": t, "cost_borne": c,
            "transparency": tr, "repair_capacity": r,
            "reciprocity": reciprocity,
        },
        "honor_score": round(honor, 3),
        "decision": decision,
    }
    audit({"event": f"honor_check.{decision.lower()}", **result})
    return result, code

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--action", type=str)
    ap.add_argument("--commitments", type=str, default="", help="comma-separated 'will not X' style")
    ap.add_argument("--cost-signal", type=str, default=None, help="none|low|medium|high")
    ap.add_argument("--affects", type=str, default="", help="comma-separated parties")
    ap.add_argument("--stdin", action="store_true", help="read a JSON payload from stdin")
    args = ap.parse_args()

    if args.stdin:
        payload = json.loads(sys.stdin.read())
    else:
        if not args.action: sys.exit("--action required (or --stdin)")
        payload = {
            "action": args.action,
            "commitments": [c.strip() for c in args.commitments.split(",") if c.strip()],
            "cost_signal": args.cost_signal,
            "affects": [a.strip() for a in args.affects.split(",") if a.strip()],
        }

    result, code = evaluate(payload)
    print(json.dumps(result, indent=2))
    sys.exit(code)

if __name__ == "__main__":
    main()
