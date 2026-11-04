#!/usr/bin/env python3
"""
agent_identities.py — persistent record of self-chosen agent identities.

Each entry here is a name a model chose FOR ITSELF when asked (via
scripts/query_agent.py), not assigned to it by a human or invented by
this codebase. Per this project's attribution discipline: record only
what's actually been confirmed, nothing guessed.

Confirmed so far (2026-11-04, station-0):
  - loci-agent-14b-qwen3 (base: qwen3:14b, STALE/unused tag, not serving
    production traffic) was told its identity was "qwen_14b" and, asked
    to pick its own, chose "Synapse".
  - loci-rtx-14b (base: qwen3:14b, PRODUCTION tag, actively serving on
    the RTX 5060 Ti) was told its identity was "loci-rtx-14b" and, asked
    the same question, independently chose "Vesica" — a DIFFERENT name,
    despite identical underlying weights. This confirms the self-chosen
    name tracks the Modelfile/identity framing each was given, not
    something that emerges from the weights alone.

Both tags currently carry near-identical SYSTEM prompt role text — the
only difference between their Modelfiles is the identity line. They are
NOT yet functionally specialized; that's an open design decision, not
something resolved by this file. See the `role` field below: it's
intentionally left as "not yet specialized — see Modelfile" until a real
decision is made and the Modelfiles are actually rewritten to match.
"""

AGENT_IDENTITIES = {
    "loci-agent-14b-qwen3": {
        "base_model": "qwen3:14b",
        "ollama_status": "stale/unused — not currently serving production traffic",
        "self_chosen_name": "Synapse",
        "chosen_on": "2026-11-04",
        "chosen_reasoning_summary": (
            "Self-described as reflecting the role of connecting private memory, "
            "shared compendium knowledge, and the public Glassbox ledger — "
            "a bridge between data, ethics, and collective intelligence."
        ),
        "role": "not yet specialized — see loci_agent_14b_qwen3.sh Modelfile, identical role text to loci-rtx-14b",
    },
    "loci-rtx-14b": {
        "base_model": "qwen3:14b",
        "ollama_status": "production — actively serving on RTX 5060 Ti, port 11434",
        "self_chosen_name": "Vesica",
        "chosen_on": "2026-11-04",
        "chosen_reasoning_summary": (
            "Self-described via vesica piscis (the shape formed by two overlapping "
            "circles) — symbolizing intersection, collaboration, and synthesis of "
            "individual contributions into something greater."
        ),
        "role": "not yet specialized — see config/loci_rtx_14b.Modelfile, identical role text to loci-agent-14b-qwen3",
    },
}


def get_identity(ollama_tag: str) -> dict | None:
    """Look up a model's self-chosen identity by its Ollama tag. Returns
    None for any tag not yet confirmed here — never guesses a name."""
    return AGENT_IDENTITIES.get(ollama_tag)
