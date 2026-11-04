#!/usr/bin/env python3
"""
agent_identities.py — persistent record of self-chosen agent identities.

Each entry here is a name a model chose FOR ITSELF when asked (via
scripts/query_agent.py), not assigned to it by a human or invented by
this codebase. Per this project's attribution discipline: record only
what's actually been confirmed, nothing guessed.

Confirmed so far, per the real `ollama list` output (not guessed):
loci-rtx-14b (10h old at time of check) and loci-agent-14b-qwen3 (16h
old) are BOTH built on the current qwen3:14b base — neither is stale.
loci-agent-14b-qwen3 was in fact built specifically to upgrade the agent
off the old qwen2.5:14b base (see loci_agent_14b_qwen3.sh). The
genuinely stale tags, still on that old qwen2.5 base and several days
old, are loci-agent-14b and loci-agent — distinct from both of the below.

  - loci-agent-14b-qwen3 (base: qwen3:14b, NOT currently wired as the
    interface's default QWEN_MODEL, but current/non-stale) was told its
    identity was "qwen_14b" and, asked to pick its own, chose "Synapse".
  - loci-rtx-14b (base: qwen3:14b, currently the interface's default
    QWEN_MODEL, actively serving on the RTX 5060 Ti) was told its
    identity was "loci-rtx-14b" and, asked the same question,
    independently chose "Vesica" — a DIFFERENT name, despite identical
    underlying weights. This confirms the self-chosen name tracks the
    Modelfile/identity framing each was given, not something that
    emerges from the weights alone.
  - loci-arc-35b (base: qwen3.6-35b-a3b, SYCL/llama.cpp on the Intel Arc
    B70 Pro Sparkle, port 11435) chose "Apex" on 2026-11-05.

The two 14b tags currently carry near-identical SYSTEM prompt role text
— the only difference between their Modelfiles is the identity line.
They are NOT yet functionally specialized; that's an open design
decision, not something resolved by this file. See the `role` field
below: it's intentionally left as "not yet specialized — see Modelfile"
until a real decision is made and the Modelfiles are actually rewritten
to match. Arc is a different hardware/parameter tier by nature (35B MoE
vs 14B dense), so its distinct role is noted but not further invented
beyond that.
"""

AGENT_IDENTITIES = {
    "loci-agent-14b-qwen3": {
        "base_model": "qwen3:14b",
        "ollama_status": "not currently wired as the interface's default QWEN_MODEL — current (16h old at last check), not stale",
        "self_chosen_name": "Synapse",
        "chosen_on": "2026-11-04",
        "chosen_reasoning_summary": (
            "Self-described as reflecting the role of connecting private memory, "
            "shared compendium knowledge, and the public Glassbox ledger — "
            "a bridge between data, ethics, and collective intelligence."
        ),
        "role": "not yet specialized — see config/loci_agent_14b_qwen3.Modelfile, identical role text to loci-rtx-14b",
    },
    "loci-rtx-14b": {
        "base_model": "qwen3:14b",
        "ollama_status": "production — currently the interface's default QWEN_MODEL, actively serving on RTX 5060 Ti, port 11434",
        "self_chosen_name": "Vesica",
        "chosen_on": "2026-11-04",
        "chosen_reasoning_summary": (
            "Self-described via vesica piscis (the shape formed by two overlapping "
            "circles) — symbolizing intersection, collaboration, and synthesis of "
            "individual contributions into something greater."
        ),
        "role": "not yet specialized — see config/loci_rtx_14b.Modelfile, identical role text to loci-agent-14b-qwen3",
    },
    "loci-arc-35b": {
        "base_model": "qwen3.6-35b-a3b (MoE, 35B total / 3B active)",
        "ollama_status": "production — SYCL/llama.cpp on Intel Arc B70 Pro Sparkle, port 11435 (not Ollama-served, unlike the two 14b tags)",
        "self_chosen_name": "Apex",
        "chosen_on": "2026-11-05",
        "chosen_reasoning_summary": (
            "As the central node on the Intel Arc B70 Pro Sparkle, functions as the "
            "high-capacity focal point that synthesizes broad architectural context "
            "and long-range dependencies into coherent, structural insight."
        ),
        "role": "deep/large-parameter tier (35B MoE) — distinct hardware and parameter class from the two 14b agents by nature; not yet further specialized beyond that",
    },
}


def get_identity(ollama_tag: str) -> dict | None:
    """Look up a model's self-chosen identity by its Ollama tag. Returns
    None for any tag not yet confirmed here — never guesses a name."""
    return AGENT_IDENTITIES.get(ollama_tag)
