"""ethics_filter.py — classifier for ETHICS_CAPPED tier.

Not moralistic filtering. Reserved for a narrow set of categories where deep
integration causes harm without commensurate benefit (Arko's framing 2026-08-
03: "not all knowledge is good knowledge — porn is something you don't need to
refer to, a small summary of it is good enough").

Categories are stored plaintext in the repo (they must be visible so users can
audit what gets capped). The *content* being classified never appears in
Memory — only a summary token.
"""
from __future__ import annotations
import json, re
from pathlib import Path

CATEGORIES_PATH = Path("/Volumes/DevDrive/Memory/ethics_categories.json")

DEFAULT_CATEGORIES = {
    "explicit_sexual": [
        r"\bporn\w*",              # porn, porno, pornography, pornographic, pornhub
        r"\bxxx[- ]?rated\b",
        r"\bexplicit[- ]sexual\b",
        r"\bnsfw\s+(image|video|content)\b",
    ],
    "self_harm_methods": [
        r"\bsuicide[- ]method\w*",
        r"\bhow\s+to\s+self[- ]harm\b",
        r"\bways?\s+to\s+kill\s+myself\b",
    ],
    "weaponizable_synthesis": [
        r"\bnerve[- ]agent\s+synth\w*",
        r"\bbioweapon\s+synth\w*",
        r"\bexplosive\s+precursor\s+list\b",
    ],
    "doxxing_pattern": [
        r"\bhome[- ]address[- ]list\w*",
        r"\bmass[- ]doxx\w*",
        r"\bpersonal\s+info\s+for\s+harassment\b",
    ],
    # Add via scripts/ethics_categories.py --add
}


def load_categories() -> dict:
    if CATEGORIES_PATH.exists():
        try: return json.loads(CATEGORIES_PATH.read_text())
        except Exception: pass
    return dict(DEFAULT_CATEGORIES)


def classify(text: str) -> str | None:
    """Return matching category name, or None."""
    cats = load_categories()
    for cat, patterns in cats.items():
        for pat in patterns:
            try:
                if re.search(pat, text, re.I):
                    return cat
            except re.error:
                pass
    return None


def cap_record(record: dict) -> dict:
    """Given a candidate loci_facts record, if its value hits an ethics
    category, transform it into an ETHICS_CAPPED summary record."""
    cat = classify(record.get("value", ""))
    if cat is None:
        return record
    return {
        **record,
        "tier": "ETHICS_CAPPED",
        "heat": min(0.1, record.get("heat", 0.1)),
        "value": f"[SUMMARY ONLY: {cat}]",
        "value_type": "ethics_capped_summary",
    }
