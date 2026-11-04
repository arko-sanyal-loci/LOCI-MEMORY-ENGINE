"""Aethel Council — the standing, level platform where humans, agents, and
AIs participate as equal members in resolving disagreement, named directly
by the user tonight: "Aethel OS is the council where all stand on a level
platform — humans, agents, AIs — for growth."

**What "level" means, confirmed with the user before building, not guessed:**
"Confidence and ethics are not negotiable, but evidence always makes
everyone heard, and no preemptive decision without every single entity's
input." Two distinct things, kept distinct here:

1. **Standing is equal, unconditionally.** A human, an agent, and an AI
   register as members the same way, through the same function, with no
   type-based privilege. `member_kind` is recorded for transparency (so a
   reader can see who's who), never for ranking — nothing in this module
   reads `member_kind` to decide whose input counts more.
2. **Confidence and ethics are NOT put to a vote.** This module has no
   voting mechanism at all, deliberately. It does not and cannot move
   `METHOD_TRUST_CEILING`, the open-interval laws, mercy/root-cause
   restoration, or any other principle — those are fixed regardless of
   how many council members agree or disagree. What this module gates is
   narrower and procedural: whether a topic's conclusion may be recorded
   as resolved BEFORE every currently-registered member has given input.
   That is a completeness check on WHO HAS BEEN HEARD, not a referendum
   on WHAT IS TRUE — truth here is still decided by the existing
   evidence machinery (`ethics.data_completeness_check`,
   `goodwill.get_method_trust`), which this module calls into rather
   than replacing.

**Standing body, not ad hoc** — confirmed with the user: membership is a
persistent registry (`register_council_member`), independent of any one
disagreement, the same way `agent_memory.py`'s logs persist independent of
any one session. A council seat, once registered, stays registered across
every future topic unless explicitly removed.

**Relationship to existing machinery, stated plainly so nothing here is
mistaken for a duplicate:**
- `ethics.record_evidence_source`/`data_completeness_check` already
  handles per-topic evidence and dissent among SOURCES. This module adds
  the membership layer underneath it: a council member is eligible to
  register evidence sources and participate in dissent resolution: this
  module does not re-implement evidence tracking, it gates on whether the
  right PEOPLE (in the broadest sense) have had the chance to.
- `agent_memory.py` is how an agent's own activity persists and feeds
  into the core ledger. An agent that is ALSO a council member can have
  both: its activity log (what it did) and its council seat (its standing
  to weigh in on disagreements) are separate, composable things.
- `goodwill.register_method_version`/`current_best_method` versions
  METHODS (ways of doing something). This module does not version facts
  or methods itself — `has_every_member_been_heard` is a yes/no
  completeness gate a caller uses before trusting any conclusion
  (including a `current_best_method` read, or a `data_completeness_check`
  result) as representative of the whole council, not a replacement for
  either.

**Honest about what this module does NOT do:** it cannot verify a
member's input was genuine, thoughtful, or correct — only that something
was recorded under their member_id for the topic. It cannot detect a
member deliberately staying silent to block consensus, nor force
participation. "Heard" means "registered input exists," nothing more.
"""
from __future__ import annotations

import time
from typing import Any, Optional

from loci_engine.ethics import ProvenanceLedger

COUNCIL_MEMBER_ROLE_TAG = "aethel_council_member"
COUNCIL_INPUT_ROLE_TAG = "aethel_council_input"
COUNCIL_MEMBER_REMOVED_ROLE_TAG = "aethel_council_member_removed"

#: Descriptive only, per the module docstring's point #1 — recorded for
#: transparency, never read anywhere in this module to weight or rank a
#: member's standing or input.
VALID_MEMBER_KINDS = ("human", "agent", "ai")


def register_council_member(
    ledger: ProvenanceLedger,
    member_id: str,
    member_kind: str,
    now: float | None = None,
) -> dict:
    """Adds `member_id` to the standing council registry, at full, equal
    standing — the same call shape regardless of whether `member_kind` is
    "human", "agent", or "ai". Calling this again for an already-registered
    member_id is not an error (idempotent re-registration, e.g. an agent
    restarting and re-asserting its seat); it does not duplicate standing,
    `list_council_members` dedupes by member_id, keeping the member active.
    """
    if member_kind not in VALID_MEMBER_KINDS:
        raise ValueError(f"member_kind must be one of {VALID_MEMBER_KINDS}, got {member_kind!r}")
    now = time.time() if now is None else now
    entry_hash = ledger.append(
        author_id=member_id,
        role_tag=COUNCIL_MEMBER_ROLE_TAG,
        payload={"member_id": member_id, "member_kind": member_kind, "t_j": now},
        now=now,
    )
    return {"member_id": member_id, "member_kind": member_kind, "entry_hash": entry_hash}


def remove_council_member(ledger: ProvenanceLedger, member_id: str, reason: str, now: float | None = None) -> dict:
    """Removes standing — an explicit, logged act (never a silent drop),
    so a later reader can see WHEN and WHY a seat was vacated, not just
    that it's absent. A removed member is excluded from
    `has_every_member_been_heard`'s requirement going forward, but every
    input they already gave stays on the ledger, untouched — removal
    affects future gating, never past record.
    """
    now = time.time() if now is None else now
    entry_hash = ledger.append(
        author_id=member_id,
        role_tag=COUNCIL_MEMBER_REMOVED_ROLE_TAG,
        payload={"member_id": member_id, "reason": reason, "t_j": now},
        now=now,
    )
    return {"member_id": member_id, "reason": reason, "entry_hash": entry_hash}


def list_council_members(ledger: ProvenanceLedger) -> list[dict]:
    """Every currently-active member (registered, not since removed),
    oldest-registered first — never reordered by kind or by anything else,
    matching this module's own "no ranking by type" principle."""
    registered: dict[str, dict] = {}
    removed: set[str] = set()
    for e in ledger._entries:
        if e.role_tag == COUNCIL_MEMBER_ROLE_TAG and isinstance(e.payload, dict):
            registered[e.payload["member_id"]] = {
                "member_id": e.payload["member_id"],
                "member_kind": e.payload["member_kind"],
                "registered_at": e.payload["t_j"],
            }
        elif e.role_tag == COUNCIL_MEMBER_REMOVED_ROLE_TAG and isinstance(e.payload, dict):
            removed.add(e.payload["member_id"])
    return [m for mid, m in sorted(registered.items(), key=lambda kv: kv[1]["registered_at"]) if mid not in removed]


def record_council_input(
    ledger: ProvenanceLedger,
    topic: str,
    member_id: str,
    input_text: str,
    now: float | None = None,
) -> dict:
    """A registered member's input on `topic` — never refused, never
    scored, never weighted here (same mercy-aligned, non-judging posture
    as `agent_memory.record_agent_activity` and
    `ethics.record_evidence_source`). This is deliberately a separate,
    lighter record than a full evidence source: a council member can
    register input on a topic ("I weighed in, here is what I said")
    without that input needing to meet `record_evidence_source`'s own
    requirements (e.g. a passing communication_health_check) — those
    stay the requirement for something being treated as formal EVIDENCE;
    this is the lower bar of "did this member get the chance to speak,
    and did they."

    Does not require `member_id` to currently be an active council member
    — input from a since-removed or never-formally-registered id is still
    recorded (the ledger does not lie about what was said), but
    `has_every_member_been_heard` only counts input from CURRENTLY active
    members toward its completeness gate.
    """
    now = time.time() if now is None else now
    entry_hash = ledger.append(
        author_id=member_id,
        role_tag=COUNCIL_INPUT_ROLE_TAG,
        payload={"topic": topic, "member_id": member_id, "input_text": input_text, "t_j": now},
        now=now,
    )
    return {"topic": topic, "member_id": member_id, "entry_hash": entry_hash}


def has_every_member_been_heard(ledger: ProvenanceLedger, topic: str) -> dict:
    """THE GATE: "no preemptive decision without every single entity's
    input," enforced as a real, checkable yes/no — not a reminder. Returns
    `all_heard: True` only if every CURRENTLY active council member has at
    least one `record_council_input` entry for this exact `topic`.

    This function makes NO claim about what conclusion the topic should
    reach, and does not and cannot touch confidence/ethics/the open-
    interval laws — per the user's own distinction, those stay fixed
    regardless of this gate's result. This gate answers one question only:
    has everyone been given a real chance to weigh in, as recorded.

    `missing_members` names exactly who hasn't spoken yet, so a caller
    knows who to go ask — the same actionable-gap posture as
    `record_conclusion`'s `unacknowledged_entries` and
    `data_completeness_check`'s `voiceless_parties`, not a bare boolean
    with no path forward.
    """
    active_members = {m["member_id"] for m in list_council_members(ledger)}
    spoken = {
        e.payload["member_id"]
        for e in ledger._entries
        if e.role_tag == COUNCIL_INPUT_ROLE_TAG
        and isinstance(e.payload, dict)
        and e.payload.get("topic") == topic
    }
    missing = sorted(active_members - spoken)
    return {
        "topic": topic,
        "all_heard": len(missing) == 0,
        "active_member_count": len(active_members),
        "missing_members": missing,
        "note": (
            "all_heard reflects only CURRENTLY active registered members "
            "and only whether input WAS recorded, not its quality or "
            "genuineness. It gates who has been heard, never what the "
            "conclusion should be -- confidence and ethics are not decided "
            "by this function or by any vote."
        ),
    }
