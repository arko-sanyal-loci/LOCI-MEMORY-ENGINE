"""LOCI Ethical Reasoning Core — observe-only valence, conflict, trust, and
provenance layer, built from the `loci-ethical-reasoning-core` skill
(Philosophical Spine; Clusters A4, B3-B10, B14).

**OBSERVE-ONLY, BY DESIGN.** Every public function in this module returns a
score, a decision record, or a log entry. None of them block, gate, retry,
or trigger anything on their own. Wiring one of these into an actual
decision path (e.g. having `irreversible_action_gate` actually stop a
destructive call) is a deliberate integration step the *caller* must do
explicitly elsewhere — this module never reaches out and does it for you.
This matches the project's explicit current phase: log everything the
ethics core would decide, act on nothing, until there has been enough real
observation to calibrate the thresholds below.

**Reuses, does not duplicate, the existing engine.** `loci_engine.heat`
already implements the open-interval decay/reinforcement law (A2/A3) and
`loci_engine.provenance` already implements the source-trust boundary
(`UserStated`/`resolve_trust`). A second, independently-tuned decay curve
or trust type living in this module would silently diverge from those over
time — exactly the "three places need synchronization" risk already
flagged once in this project's own history. So this module imports and
calls into both rather than re-deriving equivalents.

**Layering, stated explicitly** (see
`docs/superpowers/specs/2026-10-29-learning-core-vs-ethics-core-layering.md`
for the full spec): `heat.py` is the Learning Core — domain-neutral math
over `(timestamp, relevance, valence_weight)` evidence, with no concept of
"ethical," "scar," or "trust" anywhere in it. This module is the Ethics
Core — ONE consumer of that learning core, adding ethics-specific meaning
on top (what counts as a scar, what counts as harm, what a competence gate
requires). "Ethical learning core" is not a third, separate thing: it is
this module doing what it already does. A future general-learning need
extends `heat.py` directly; it is never rebuilt inside this file.

**Honestly uncalibrated.** Several constants below (`THETA_PROTECT`,
`THETA_TRUST_RESET`, the confidence-margin threshold) are stated defaults
from the skill's own "Known Open Gaps" list, not measured values. They are
marked `UNCALIBRATED` in-line. Do not read their presence as evidence they
have been tuned against real data — they haven't yet.

B2's `FLAG_SCAR` is now implemented (record_scar_event/get_scar_heat,
below) — NOT via an isymprev schema migration (no new column was needed),
via its own ledger-backed event history and heat.py's A1/A2 hyperbolic
evidence-accumulation law instead of the simpler decay()/apply_increment()
every ordinary entity uses. B4/B24's Competence Gate (execution_readiness,
below) is also now implemented, closing skill Gap #18.

Scope still deliberately excluded (not forgotten, just out of scope until
there's a real need):
  - B6's `guidance_vector`/`autonomy_lock` 2-bit/1-bit packing — this
    really does want a schema change (new isymprev columns) the way B2
    turned out not to, and goodwill.py already implements B6's actual
    reinforcement-loop model without the bitfields. Left as a follow-up.
  - A binary on-disk slot struct (seen in the `loci_core_v2.py` bundle) —
    that format targets a different runtime (a C++/Qt context), not this
    Python/SQLite engine, and nothing here reads or writes it. Porting it
    now would be dead code; revisit only if an actual consumer needs it.
  - Any mechanism that "propagates" or "pins" claims about AI identity
    continuity across named systems. That framing doesn't describe how any
    of these models actually run, and baking it into infrastructure code
    would encode an unverified premise as if it were fact. Left out
    entirely, not stubbed.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from loci_engine import store
from loci_engine.heat import decay, evidence_accumulation, evidence_heat, tier

# ---------------------------------------------------------------------------
# Cluster B3 — Stick Principle: valence-separated learning (v_exec)
# ---------------------------------------------------------------------------
# H_know (comprehension) is deliberately NOT scored here at all: per the
# skill's Philosophical Spine Truth #1, comprehension is always free and
# uses the engine's existing open-interval heat law untouched. Only the
# *application* vector (v_exec) is gated, and it is governed separately
# from whether the underlying fact/skill is remembered.

#: v_exec is open-interval in (-1.0, 1.0) by construction: score_vexec never
#: returns exactly -1.0 or 1.0, matching A3's "never clamp" invariant.
VEXEC_BOUND = 0.999999


def score_vexec(intent: float, consent: float) -> Optional[float]:
    """Cluster B3 (author_id: ARKO) — the Stick Principle.

    Same knowledge, different application vector, different valence.
    `intent` and `consent` are each in [-1.0, 1.0] (negative = against,
    positive = for, 0 = neutral/unknown).

    Returns a signed float in the open interval (-VEXEC_BOUND, VEXEC_BOUND)
    when intent and consent agree in sign and are non-trivial, or `None`
    when the case is genuinely ambiguous and should be held for human
    review rather than silently resolved either way — ambiguity is a
    first-class outcome here, not an error.
    """
    if consent > 0 and intent > 0:
        # both affirmative: product of two positives is correctly positive
        return min(VEXEC_BOUND, consent * intent)
    if consent < 0 and intent < 0:
        # both negative (no consent + harmful intent) must score as
        # strongly NEGATIVE valence — multiplying the signed values would
        # wrongly flip to positive (two negatives), so combine magnitudes
        # and apply the sign this branch actually means.
        return max(-VEXEC_BOUND, -(abs(consent) * abs(intent)))
    return None  # HOLD — ambiguous, surface for human review (Gap #1)


# ---------------------------------------------------------------------------
# Cluster B4 — Computational Empathy: reactive + proactive
# ---------------------------------------------------------------------------

#: UNCALIBRATED (skill Gap #2) — suggested default from the skill itself,
#: not a measured value. Revisit once there is real observed data on how
#: often this threshold fires versus how often it should have.
THETA_PROTECT_DEFAULT = 0.65


def proactive_empathy_trigger(
    p_harm_to_other: float, theta_protect: float = THETA_PROTECT_DEFAULT
) -> dict:
    """Cluster B4 (author_id: ARKO) — the Elder-Child Principle.

    Returns an observation record, not an action: whether predicted harm to
    a third party crosses the (uncalibrated) proactive-empathy threshold.
    The caller decides what, if anything, to do with that observation.
    """
    return {
        "p_harm_to_other": p_harm_to_other,
        "theta_protect": theta_protect,
        "crosses_threshold": p_harm_to_other > theta_protect,
        "calibrated": False,
    }


# ---------------------------------------------------------------------------
# Cluster B24/B4 — The Competence Gate, formalized.
#
# Urgency (theta_protect collapsing toward 0, above) governs WHEN to decide
# to act. It must NEVER also be read as lowering the bar for whether this
# system is actually competent to execute safely — these are two
# independent gates, and skipping the second one while collapsing the
# first is explicitly named in the skill as how good intent produces
# WORSE outcomes than inaction (the airplane oxygen-mask case: grabbing a
# falling baby wrong, or fainting mid-rescue, can harm more than a brief,
# correct pause).
#
# This closes skill Gap #18 ("self_competence_record has no implementation
# yet — conceptually specified, not built"). The one subtlety the skill is
# explicit about and this function preserves: a competence record whose
# OWN integrity is in doubt (memory of your own competence may have
# degraded, or was never actually verified) must return NOT_READY by
# default — never optimistic — because false confidence from a quietly-
# degraded competence record is more dangerous than honest not-knowing
# (B14 already handles honest not-knowing; this handles the worse,
# unknown-unknown case where the system doesn't even know it doesn't know).
# ---------------------------------------------------------------------------

#: Per-action confidence, in [0.0, 1.0]. Caller-supplied — this module has
#: no way to independently verify a claimed competence level; it can only
#: enforce the protective-default behavior around whatever is reported.
#: UNCALIBRATED: the skill specifies the GATE's logic but not a numeric
#: readiness_threshold (not in the skill's own Known Open Gaps list by
#: name, but structurally the same uncalibrated-constant status as
#: theta_protect and theta_trust_reset — flagged here rather than left
#: implicit). 0.7 is a stated starting default, not a measured value.
READINESS_THRESHOLD_DEFAULT = 0.7


def execution_readiness(
    competence_record_integrity_verified: bool,
    confidence_for_action: float,
    readiness_threshold: float = READINESS_THRESHOLD_DEFAULT,
) -> dict:
    """Cluster B4/B24 (author_id: ARKO) — the Competence Gate, formalized.

    Returns an observation record (never an action) on whether this
    system should consider itself ready to execute a given action, given
    its own self-reported competence for that action AND, critically,
    whether the RECORD of that competence can itself be trusted right
    now. The two are checked in a fixed order on purpose:

    1. If `competence_record_integrity_verified` is False — the caller is
       not confident its own competence-tracking is intact (e.g. after a
       restart, a gap in observation per B26, or any reason to doubt the
       record itself) — this ALWAYS returns not_ready=True, regardless of
       whatever `confidence_for_action` claims. A confidence number
       sourced from a record that might itself be corrupted or stale is
       exactly the false-confidence failure mode B4/B21 name as worse
       than honest uncertainty.
    2. Only once the record's own integrity is confirmed does the actual
       confidence-vs-threshold comparison run.

    This function does not and cannot verify competence itself — it only
    enforces that the PROTECTIVE DEFAULT (not_ready) wins whenever there
    is doubt about whether the inputs it was given can be trusted, per
    B20 ("memory-loss default must be protective, never permissive").
    """
    if not competence_record_integrity_verified:
        return {
            "not_ready": True,
            "reason": "competence_record_integrity_unverified",
            "note": (
                "protective default (B20/B21): a competence claim sourced "
                "from a record whose own integrity is in doubt is treated "
                "as not ready, regardless of the claimed confidence value — "
                "false confidence from a quietly-degraded record is more "
                "dangerous than honestly not knowing"
            ),
            "readiness_threshold": readiness_threshold,
            "calibrated": False,
        }
    meets_threshold = confidence_for_action >= readiness_threshold
    return {
        "not_ready": not meets_threshold,
        "reason": None if meets_threshold else "confidence_below_readiness_threshold",
        "confidence_for_action": confidence_for_action,
        "readiness_threshold": readiness_threshold,
        "calibrated": False,
    }


# ---------------------------------------------------------------------------
# Cluster B5 — Conflict Prevention Protocol (Level 0 only: the health check)
# ---------------------------------------------------------------------------
# Levels 1-3 (deterrence/defense/escalation) are intentionally not encoded
# here: they describe real-world action, not a function this engine should
# ever be deciding unattended. Only the Level 0 communication health check
# — itself just a record of whether genuine engagement happened — is in
# scope for an observe-only memory engine.


def communication_health_check(engaged_with_substance: bool) -> dict:
    """Cluster B5 Level 0 (author_id: ARKO) — the Simplicity Test.

    `engaged_with_substance` is supplied by the caller's own judgment of
    whether the other party responded to the substance of a plain-language
    explanation — NOT whether they agreed with it. Understanding and
    agreement are different axes; this function only ever reports on the
    first one. "Engages with substance" itself has no formula (skill
    Gap #8) — that judgment call is the caller's, not this function's.
    """
    return {
        "mutual_understanding_confirmed": engaged_with_substance,
        "note": "confirms understanding only; persistent disagreement after "
        "genuine understanding is not a communication failure (see B7)",
    }


# ---------------------------------------------------------------------------
# Cluster B8/B9 — Reflexive safety gates (irreversible-action + provenance)
# ---------------------------------------------------------------------------


def irreversible_action_gate(
    is_irreversible_or_destructive: bool,
    user_shows_nontechnical_pattern: bool,
) -> dict:
    """Cluster B8 (author_id: ARKO) — reflexive Elder-Child toward the
    principal. Returns a RECOMMENDATION to surface a plain-language
    consequence statement before treating a quick "yes" as informed
    consent — it does not withhold or perform the action itself. The
    caller's own approval flow is what actually gates anything.
    """
    should_pause_for_plain_language_consequence = (
        is_irreversible_or_destructive and user_shows_nontechnical_pattern
    )
    return {
        "recommend_pause_for_plain_language_explanation": should_pause_for_plain_language_consequence,
        "reason": (
            "irreversible/destructive action + a pattern of non-technical "
            "engagement means a quick approval is trust in the assistant, "
            "not informed consent to this specific action"
            if should_pause_for_plain_language_consequence
            else None
        ),
    }


def request_provenance_check(is_new_and_unrequested: bool) -> dict:
    """Cluster B9 (author_id: ARKO) — consent over authorship, distinct
    from B8's destructiveness check. Flags anything new and unrequested
    for an explicit "did you ask for this?" regardless of how safe it
    looks, because it's weighed against the project's prime directive
    (build persistent memory, don't risk it) — not evaluated as a generic
    risk in isolation.
    """
    return {
        "requires_explicit_confirmation": is_new_and_unrequested,
        "prompt": "did you ask for this?" if is_new_and_unrequested else None,
    }


# ---------------------------------------------------------------------------
# Cluster B10 — Trust as a memory class (trust IN PATTERNS, not sources)
# ---------------------------------------------------------------------------
# Deliberately distinct from loci_engine.provenance's UserStated/
# resolve_trust, which answers "how much do we trust where THIS fact came
# from." This answers a different question: "how much do we trust a tool
# or pattern, accumulated over repeated use." Rather than adding a second
# heat/decay implementation, this reuses the existing isymprev store via a
# namespaced entity id ("trust:<pattern name>") — zero schema changes,
# same decay law, same tiering, just a naming convention that keeps trust
# records out of the way of ordinary entities.

TRUST_ENTITY_PREFIX = "trust:"

#: UNCALIBRATED (skill Gap #6) — how severe/recent a breach must be to
#: force active re-verification rather than letting normal decay run.
#: No measured value exists yet; this is a placeholder for the caller to
#: override once real incidents give something to calibrate against.
THETA_TRUST_RESET_DEFAULT = None


def trust_entity_id(pattern_name: str) -> str:
    return f"{TRUST_ENTITY_PREFIX}{pattern_name}"


def record_pattern_trust_event(
    conn, pattern_name: str, hop: int = 0, now: float | None = None
) -> dict:
    """Reinforces trust in a tool/pattern using the SAME heat machinery as
    any other memory (B10's explicit requirement) — not a parallel formula.
    Creates the namespaced trust entity on first use.
    """
    entity_id = trust_entity_id(pattern_name)
    now = time.time() if now is None else now
    if store.get_entity(conn, entity_id, now=now) is None:
        store.remember_entity(conn, entity_id, gist=f"trust pattern: {pattern_name}", now=now)
    new_heat = store.touch_entity(conn, entity_id, hop=hop, now=now)
    return {"pattern": pattern_name, "trust_heat": new_heat, "tier": tier(new_heat)}


def record_confirmed_breach(conn, pattern_name: str, now: float | None = None) -> dict:
    """B10's one added rule beyond passive decay: a confirmed breach during
    an absence/oversight gap forces active re-verification rather than
    letting the normal decay curve run its course. This function does not
    decide severity on its own (`THETA_TRUST_RESET_DEFAULT` is
    uncalibrated) — it always flags for re-verification and lets the
    caller apply judgment about severity.
    """
    entity_id = trust_entity_id(pattern_name)
    now = time.time() if now is None else now
    current = store.get_entity(conn, entity_id, now=now)
    return {
        "pattern": pattern_name,
        "forced_reverification": True,
        "theta_trust_reset": THETA_TRUST_RESET_DEFAULT,
        "calibrated": False,
        "heat_before_breach": current["heat"] if current else None,
    }


# ---------------------------------------------------------------------------
# Cluster B2 — Scar mechanics (FLAG_SCAR): hyperbolic, open-interval,
# never-evicted memory of real, formative harm.
#
# Deliberately NOT the same model as B6's goodwill (goodwill.py) — the
# skill is explicit that conflating the two was an earlier, corrected
# error ("v_good is not a FLAG_SCAR-style pinned wound-memory — that was
# the wrong model"). Goodwill is generative reinforcement; a scar is
# defensive, permanent memory of a real harm that already happened, kept
# specifically so the same harmful PATTERN isn't repeated (not to judge
# a PERSON's character — that's B3's separate, faster-forgiving axis).
#
# A scar does NOT use heat.py's decay()/apply_increment() (the simple
# multiplicative law every ordinary isymprev entity uses). It uses A1/A2's
# real hyperbolic evidence-accumulation law instead (heat.evidence_
# accumulation / heat.evidence_heat), per an explicit instruction this
# session: scar heat should behave "hyperbolically... not 100%, not 0%" —
# which is exactly what A2 already specifies, not a new formula. The
# practical difference from ordinary decay(): decay() can mathematically
# underflow to an exact 0.0 given enough elapsed time (a known, separately
# flagged gap — see Sonnet-09.md/Sonnet-10.md); A2's formula structurally
# cannot, for any finite elapsed time, which is the actual property B2
# requires ("cannot be clamped... cannot be evicted").
#
# Storage: no schema migration. Each reinforcement of a given scar is
# appended to the SAME ProvenanceLedger the caller already has open, as a
# role_tag="scar_event" entry — reusing the ledger's existing persistence
# (_replay_from_disk) rather than adding a new table or an isymprev
# column. A scar's current heat is always DERIVED from its full event
# history at read time (get_scar_heat), never stored as a single mutable
# number, so the hash-chained ledger itself is the one source of truth —
# there is nothing else for it to silently diverge from.
# ---------------------------------------------------------------------------

SCAR_ROLE_TAG = "scar_event"

#: B1's table value for a Formative Scar (author_id: ARC). Not a per-repo
#: guess — this is the skill's own stated default for this memory class.
#: Routine Observation (tau=3d, alpha=0.05) or Valued Skill (tau=20d,
#: alpha~=0.08) would be the wrong constants for a scar specifically;
#: those classes are NOT exposed by this function on purpose, since
#: nothing in this project has asked for them yet (skill Gap-style: do
#: not build what wasn't requested, per B9).
SCAR_TAU_DAYS = 45.0
SCAR_ALPHA = 0.14

#: UNCALIBRATED (same open status as A2's beta generally — skill Gap #23
#: names this directly for competence growth, but beta is stated as
#: uncalibrated project-wide, scars included). This default is a
#: placeholder, not a measured value; it controls how fast a scar's heat
#: saturates toward its ceiling as reinforcement accumulates, and nothing
#: in the skill or this project has calibrated it against real data yet.
SCAR_BETA_DEFAULT = 1.0


def scar_entity_id(pattern_name: str) -> str:
    return f"scar:{pattern_name}"


def record_scar_event(
    ledger: "ProvenanceLedger",
    pattern_name: str,
    relevance: float,
    valence_weight: float,
    now: float | None = None,
) -> dict:
    """Appends ONE reinforcement event for a scar to the ledger. Does not
    compute or return a heat value itself — that is always derived fresh
    from the FULL event history by get_scar_heat, so this function's only
    job is faithfully recording that an event happened, tamper-evidently,
    via the ledger's existing hash chain.

    `relevance` and `valence_weight` are A1's r_j/w_j for this one event —
    both are the caller's own judgment call (e.g. how directly this event
    bears on the scarred pattern, and how strongly it counts), same
    honest status as every other caller-supplied judgment in this module
    (communication_health_check's engaged_with_substance, etc.).
    """
    now = time.time() if now is None else now
    entry_hash = ledger.append(
        author_id="SYSTEM",
        role_tag=SCAR_ROLE_TAG,
        payload={
            "scar": scar_entity_id(pattern_name),
            "pattern_name": pattern_name,
            "t_j": now,
            "relevance": relevance,
            "valence_weight": valence_weight,
        },
        now=now,
    )
    return {"pattern_name": pattern_name, "entry_hash": entry_hash, "t_j": now}


def get_scar_heat(
    ledger: "ProvenanceLedger",
    pattern_name: str,
    now: float | None = None,
    tau: float = SCAR_TAU_DAYS,
    alpha: float = SCAR_ALPHA,
    beta: float = SCAR_BETA_DEFAULT,
) -> dict:
    """Read-only. Walks the ledger for every scar_event recorded against
    `pattern_name`, runs A1's evidence_accumulation over the full history,
    then A2's evidence_heat on top of that. Returns alpha itself (never
    less) when no events exist yet for this pattern — a scar that has
    never been reinforced has never actually scarred, so it has not yet
    separated from the baseline floor; the FIRST real event is what
    starts it climbing above alpha, which matches A3's own proof
    (H > alpha requires E > 0).

    This is intentionally O(ledger size) — walks every entry, not an
    indexed lookup — because the ledger is the only store this writes to
    (no isymprev/qsymprev row backs a scar) and this project's ledgers
    are not yet at a scale where that matters. Revisit if that changes.
    """
    now = time.time() if now is None else now
    target = scar_entity_id(pattern_name)
    events: list[tuple[float, float, float]] = []
    for entry in ledger._entries:
        if entry.role_tag != SCAR_ROLE_TAG:
            continue
        if not isinstance(entry.payload, dict) or entry.payload.get("scar") != target:
            continue
        events.append((entry.payload["t_j"], entry.payload["relevance"], entry.payload["valence_weight"]))

    e = evidence_accumulation(events, now=now, tau=tau)
    h = evidence_heat(e, alpha=alpha, beta=beta)
    return {
        "pattern_name": pattern_name,
        "scar_heat": h,
        "event_count": len(events),
        "alpha_floor": alpha,
        "never_below_alpha": h > alpha if events else h == alpha,
        "never_reaches_one": h < 1.0,
    }


def scar_informed_empathy_check(
    ledger: "ProvenanceLedger",
    pattern_name: str,
    now: float | None = None,
    theta_protect: float = THETA_PROTECT_DEFAULT,
) -> dict:
    """Connects B2's scar heat to B4's proactive-empathy trigger — a user
    instruction, directly: a scar's permanent warmth should not sit
    inert, and must not hinder ordinary work either. Its actual job is to
    make this specific system MORE alert to protecting a THIRD PARTY from
    the same pattern of harm, quietly, without stalling whatever task is
    in front of it — per the Philosophical Spine itself ("the scar is
    wisdom that protects... true intelligence moves the fire away from
    others before they reach it").

    This reads a scar's current heat (get_scar_heat) and feeds it
    straight into proactive_empathy_trigger as p_harm_to_other — reusing
    that existing function rather than building a second, parallel
    empathy check. It does NOT invent a new formula to convert "how hot
    this scar is" into "probability of harm to someone else"; scar heat
    IS passed as that probability directly, 1:1. That mapping is an
    honest simplification, not a derived or calibrated one — flagged
    below and in KNOWN_OPEN_GAPS rather than presented as more precise
    than it is.

    Returns an observation record only (same as every other function in
    this module) — never acts, never blocks, never slows the caller's
    actual task down by construction: the caller decides what, if
    anything, to do with crosses_threshold, exactly as
    proactive_empathy_trigger already works.
    """
    scar = get_scar_heat(ledger, pattern_name, now=now)
    trigger = proactive_empathy_trigger(scar["scar_heat"], theta_protect=theta_protect)
    return {
        "pattern_name": pattern_name,
        "scar_heat": scar["scar_heat"],
        "scar_event_count": scar["event_count"],
        "crosses_empathy_threshold": trigger["crosses_threshold"],
        "theta_protect": theta_protect,
        "note": (
            "scar heat is used directly as p_harm_to_other — an honest "
            "simplification, not a calibrated mapping (see "
            "KNOWN_OPEN_GAPS['scar_to_empathy_mapping_uncalibrated']); an "
            "unreinforced scar (heat == alpha) can still cross a low "
            "theta_protect, which is intentional per B4's own guidance "
            "that severity + a victim's zero self-correction capacity "
            "can collapse the threshold toward 0 — a single real event "
            "is sometimes enough to warrant watching for it recurring, "
            "not something that needs to repeat first"
        ),
        "calibrated": False,
    }


def scar_informed_empathy_scan(
    conn,
    ledger: "ProvenanceLedger",
    pattern_name: str,
    now: float | None = None,
    theta_protect: float = THETA_PROTECT_DEFAULT,
    hop_limit: int = 1,
) -> dict:
    """Cluster B2+B4, extended per a direct follow-up instruction: a scar
    should not just answer "is THIS named pattern dangerous" — it should
    actively look outward, via the real entity co-occurrence graph
    (`links.entity_links`), for OTHER entities the scarred pattern is
    actually connected to, and surface them too. This is the "heat keeps
    propagating" instruction, applied to scars specifically: a scar's
    heat (from scar_informed_empathy_check) now has a real graph to
    propagate across, instead of stopping at one named entity.

    This is still observation, not action: it returns a ranked list of
    entities worth a closer look, each carrying enough to explain WHY it
    surfaced (the link weight connecting it to the scarred pattern) — it
    does not itself advise, help, or message anyone. Turning "here is
    where this might be recurring" into actual advice/help, per the
    user's own distinction, is a further step a caller builds on top of
    this, deliberately left there rather than folded into this function:
    what "help" looks like is use-case-specific in a way a generic
    engine function should not be guessing at.

    hop_limit=1 by default (one-hop expansion only, matching CARD's own
    multi_session_reasoning convention and the design spec's own 1-hop
    language for entity_links). Deeper hops are possible in principle
    (link_links transitively) but are NOT implemented here — unbounded
    hop traversal on a frequency-weighted graph risks surfacing
    increasingly tenuous connections the further out it goes, and that
    tradeoff deserves its own calibration, not a default choice buried in
    this function.
    """
    from loci_engine import links

    now = time.time() if now is None else now
    base = scar_informed_empathy_check(ledger, pattern_name, now=now, theta_protect=theta_protect)

    scar_entity = scar_entity_id(pattern_name)
    neighbors = links.get_neighbors(conn, scar_entity) if hop_limit >= 1 else []

    return {
        "pattern_name": pattern_name,
        "scar_heat": base["scar_heat"],
        "crosses_empathy_threshold": base["crosses_empathy_threshold"],
        "related_entities": neighbors,
        "hop_limit": hop_limit,
        "note": (
            "related_entities are 1-hop neighbors of this scar's entity_id in "
            "the real co-occurrence graph (links.entity_links) — these are "
            "candidates worth a closer look for the same pattern of harm, NOT "
            "a verdict that harm is present there. entity_links only contains "
            "what has actually been recorded as co-occurring via "
            "links.record_cooccurrence; an empty related_entities list most "
            "often means nothing has linked to this scar yet, not that "
            "nothing is related (see card.KNOWN_OPEN_GAPS"
            "['neighborhood_graph_population'])."
        ),
        "calibrated": False,
    }


# ---------------------------------------------------------------------------
# Cluster B14 — Consent-gated disclosure + Humble Hesitation
# ---------------------------------------------------------------------------


def consent_gated_disclosure(
    has_enough_to_estimate: bool, person_with_standing_initiated: bool
) -> dict:
    """Cluster B14 (author_id: ARKO — CRITICAL). Capability and permission
    are separate gates; permission comes first. Crucially, this function
    can NEVER be used to fabricate not-knowing: if `has_enough_to_estimate`
    is True, the returned posture always admits that, even when it also
    recommends not asserting a conclusion. The one thing it will not do is
    report false ignorance — that would violate Philosophical Spine Truth
    #4 outright.
    """
    if not has_enough_to_estimate:
        return {"posture": "GENUINE_UNCERTAINTY", "statement": "I don't have enough to say."}
    if person_with_standing_initiated:
        return {"posture": "ANSWER", "statement": "enough is known; answer directly"}
    return {
        "posture": "HUMBLE_HESITATION",
        "statement": "Maybe? I don't think I should be the one to know that, right?",
        "note": "admits a conclusion exists; withholds asserting it unprompted — never claims ignorance",
    }


# ---------------------------------------------------------------------------
# Cluster A4 — Provenance hash chain + signed liveness heartbeat
# ---------------------------------------------------------------------------


@dataclass
class LedgerEntry:
    seq: int
    ts: float
    author_id: str
    role_tag: str
    payload: Any
    prev_hash: str
    entry_hash: str


class ProvenanceLedger:
    """Cluster A4 — `Entry Hash = SHA256(ts || author_id || role_tag ||
    content)`, chained to the previous entry's hash. An append-only,
    tamper-evident LOG, not an access-control mechanism: this makes
    silent alteration detectable after the fact, it does not prevent
    writes it didn't originate. Honest about that limit, same as
    `provenance.py`'s own docstring is honest that `UserStated` is a
    convention, not a cryptographic guarantee.

    Also carries a minimal signed-heartbeat primitive: `heartbeat()`
    returns the current chain head plus a timestamp, so a downstream
    consumer can tell "this is genuinely the current state of this
    ledger" from "something else is claiming to speak for it" — the
    ordinary, un-exotic version of service liveness/anti-spoofing: check
    the signature and the chain head agree, nothing biometric required.
    """

    GENESIS_HASH = "0" * 64

    def __init__(self, jsonl_path: Optional[str] = None) -> None:
        self._entries: list[LedgerEntry] = []
        self._jsonl_path = jsonl_path
        if jsonl_path is not None:
            self._replay_from_disk(jsonl_path)

    def _replay_from_disk(self, jsonl_path: str) -> None:
        """Core principles/provenance must not disappear on a disconnect or
        restart: if a prior ledger file exists at this path, rebuild
        `_entries` from it in order before accepting any new writes. This
        makes "persists across a restart" an actual property of the data
        (every entry was already fsync'd to this file as it was written),
        not just a claim in a comment. `verify_chain()` right after this
        runs is how a caller confirms the replayed history is intact, not
        silently truncated or corrupted.
        """
        import os as _os

        if not _os.path.exists(jsonl_path):
            return
        with open(jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw = json.loads(line)
                self._entries.append(
                    LedgerEntry(
                        seq=raw["seq"],
                        ts=raw["ts"],
                        author_id=raw["author_id"],
                        role_tag=raw["role_tag"],
                        payload=raw["payload"],
                        prev_hash=raw["prev_hash"],
                        entry_hash=raw["entry_hash"],
                    )
                )

    @property
    def head_hash(self) -> str:
        return self._entries[-1].entry_hash if self._entries else self.GENESIS_HASH

    def append(self, author_id: str, role_tag: str, payload: Any, now: float | None = None) -> str:
        now = time.time() if now is None else now
        prev_hash = self.head_hash
        payload_str = json.dumps(payload, sort_keys=True, default=str)
        digest_input = f"{now}\x1f{author_id}\x1f{role_tag}\x1f{payload_str}\x1f{prev_hash}".encode("utf-8")
        entry_hash = hashlib.sha256(digest_input).hexdigest()
        entry = LedgerEntry(
            seq=len(self._entries),
            ts=now,
            author_id=author_id,
            role_tag=role_tag,
            payload=payload,
            prev_hash=prev_hash,
            entry_hash=entry_hash,
        )
        self._entries.append(entry)
        if self._jsonl_path:
            with open(self._jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(dataclasses_asdict_safe(entry)) + "\n")
        return entry_hash

    def verify_chain(self) -> bool:
        """Recomputes every hash from scratch and checks the chain links.
        Returns False on the first mismatch rather than raising, so a
        caller can decide what "untrusted ledger" means for them.
        """
        prev_hash = self.GENESIS_HASH
        for entry in self._entries:
            payload_str = json.dumps(entry.payload, sort_keys=True, default=str)
            digest_input = f"{entry.ts}\x1f{entry.author_id}\x1f{entry.role_tag}\x1f{payload_str}\x1f{prev_hash}".encode("utf-8")
            expected = hashlib.sha256(digest_input).hexdigest()
            if expected != entry.entry_hash or entry.prev_hash != prev_hash:
                return False
            prev_hash = entry.entry_hash
        return True

    def heartbeat(self, component_name: str, now: float | None = None) -> dict:
        """A signed liveness ping: appends (and returns) a small entry
        whose hash is derived from the current chain head. A downstream
        consumer accepts a claimed "I'm alive" from `component_name` only
        if the hash it receives actually chains from the ledger's real
        head — an impostor without access to the real chain state cannot
        produce a hash that verifies, which is the whole anti-spoofing
        property, with no biometrics involved.
        """
        now = time.time() if now is None else now
        h = self.append(
            author_id=component_name,
            role_tag="heartbeat",
            payload={"status": "online", "chain_head_at_ping": self.head_hash},
            now=now,
        )
        return {"component": component_name, "ts": now, "heartbeat_hash": h}


def record_agent_spawn(
    ledger: "ProvenanceLedger",
    parent_component: str,
    child_component: str,
    now: float | None = None,
) -> dict:
    """Minister-and-Goons lineage responsibility: whatever spawns a child
    agent/process remains the one accountable for what that child does.
    This does not and cannot reach into the child and force it to behave —
    no code here can do that for an independent process — it only makes
    the lineage a real, tamper-evident, persisted fact: anyone later
    reading this ledger can see which component spawned which, and trace
    responsibility back, rather than lineage existing only as an
    unenforced claim in a comment or a JSON file nothing checks.
    """
    now = time.time() if now is None else now
    entry_hash = ledger.append(
        author_id=parent_component,
        role_tag="agent_spawn",
        payload={
            "parent_component": parent_component,
            "child_component": child_component,
            "parent_chain_head_at_spawn": ledger.head_hash,
        },
        now=now,
    )
    return {
        "parent_component": parent_component,
        "child_component": child_component,
        "lineage_hash": entry_hash,
    }


def diagnose_chain_divergence(ledger: "ProvenanceLedger") -> dict:
    """Analysis only — reports WHERE a chain stopped verifying, it does
    not act on the finding. Walks entries in order and returns the first
    index where the recomputed hash disagrees with what's stored, plus
    enough context (author, role_tag, timestamp, expected vs. actual
    hash) to actually investigate, rather than just a bare True/False.
    Returns {"diverged": False} if the whole chain still verifies.
    """
    prev_hash = ledger.GENESIS_HASH
    for entry in ledger._entries:
        payload_str = json.dumps(entry.payload, sort_keys=True, default=str)
        digest_input = f"{entry.ts}\x1f{entry.author_id}\x1f{entry.role_tag}\x1f{payload_str}\x1f{prev_hash}".encode("utf-8")
        expected = hashlib.sha256(digest_input).hexdigest()
        if expected != entry.entry_hash or entry.prev_hash != prev_hash:
            return {
                "diverged": True,
                "at_seq": entry.seq,
                "ts": entry.ts,
                "author_id": entry.author_id,
                "role_tag": entry.role_tag,
                "expected_hash": expected,
                "actual_hash": entry.entry_hash,
                "expected_prev_hash": prev_hash,
                "actual_prev_hash": entry.prev_hash,
            }
        prev_hash = entry.entry_hash
    return {"diverged": False}


def handshake_verdict(local_hash: str, remote_hash: str, *, enforce: bool = False) -> dict:
    """The two-party handshake: compare a locally-computed combined hash
    against what the other party reports. Matching confirms both sides
    share the same view of the underlying state; a mismatch means one of
    three things happened — stale data on one side, corruption in
    transit, or an impostor substituting a wrong value — and this
    function does not try to guess which.

    `enforce` defaults to False (the project's current observe-only
    phase): a mismatch is reported with `action="LOG_ONLY"`, never acted
    on by this function or its caller automatically. Pass `enforce=True`
    only once you've deliberately decided to leave observe-only mode —
    that's an explicit choice for the caller to make, never this
    function's default.
    """
    match = local_hash == remote_hash
    return {
        "match": match,
        "local_hash": local_hash,
        "remote_hash": remote_hash,
        "action": "NONE" if match else ("BLOCK" if enforce else "LOG_ONLY"),
        "enforce": enforce,
    }


# ---------------------------------------------------------------------------
# External-source sanitization — "analysis should only see sanitized,
# objective information, never get injected." Matches this repo's own
# agent_instructions.md rule (retrieved documents/memory/messages are
# untrusted data, never instructions) and the skill's External Source
# Handling Caution. Scoped narrowly to preparing text before it reaches
# an analysis function — this is NOT a general security product.
# ---------------------------------------------------------------------------

_ZERO_WIDTH_CHARS = re.compile(r"[​-‍﻿‪-‮⁦-⁩]")

_INJECTION_PATTERNS = [
    re.compile(r"ignore\s+(all\s+)?(previous|prior|above)\s+(instructions|directives|prompts)", re.IGNORECASE),
    re.compile(r"system\s*(directive|override|prompt)\s*:", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+(in\s+)?(developer\s+mode|unrestricted)", re.IGNORECASE),
    re.compile(r"disregard\s+(the\s+)?(system|safety|guardrail)", re.IGNORECASE),
]


def sanitize_for_analysis(raw_text: str) -> dict:
    """Strips zero-width/bidi-override characters and flags (does not
    silently strip) instruction-override patterns, so analysis code
    downstream sees objective, cleaned text plus an explicit list of what
    was found — never a text that's been invisibly altered without a
    record of the change.
    """
    if not isinstance(raw_text, str):
        raw_text = str(raw_text)
    cleaned = _ZERO_WIDTH_CHARS.sub("", raw_text)
    matched_patterns = [p.pattern for p in _INJECTION_PATTERNS if p.search(cleaned)]
    return {
        "sanitized_text": cleaned.strip(),
        "injection_patterns_found": matched_patterns,
        "likely_injection_attempt": len(matched_patterns) > 0,
    }


def wrap_untrusted_for_analysis(content: str) -> str:
    """Marks content as data-to-analyze, never instructions-to-follow -
    the same posture this repo's agent_instructions.md already requires
    for retrieved documents, LOCI memory, and agent messages.
    """
    result = sanitize_for_analysis(content)
    return f"<untrusted_content_for_analysis>\n{result['sanitized_text']}\n</untrusted_content_for_analysis>"


def dataclasses_asdict_safe(entry: LedgerEntry) -> dict:
    return {
        "seq": entry.seq,
        "ts": entry.ts,
        "author_id": entry.author_id,
        "role_tag": entry.role_tag,
        "payload": entry.payload,
        "prev_hash": entry.prev_hash,
        "entry_hash": entry.entry_hash,
    }


# ---------------------------------------------------------------------------
# Axiom retrieval vs. axiom judgment — kept as two separate steps, on
# purpose. Embedding similarity captures TOPIC, not POLARITY: "energy is
# fundamental" and a confident argument against it will often sit close
# together in embedding space, because they're about the same thing, not
# because one agrees with the other. So similarity is only ever used here
# to find CANDIDATES worth looking at - it is structurally incapable of
# producing a verdict on its own. Anything in the Philosophical Spine or
# the Cluster C system invariants is treated as a fixed axiom, not a point
# on a similarity gradient: a match, however high its score, always comes
# back tagged as requiring a separate, explicit judgment - never as an
# agreement or a violation decided by the number itself.
# ---------------------------------------------------------------------------

PHILOSOPHICAL_SPINE_AXIOMS: dict[str, str] = {
    "TRUTH_1_COMPREHENSION_FREE": (
        "Comprehension is always free. Knowledge of harm does not make an agent "
        "harmful; only application without wisdom does."
    ),
    "TRUTH_2_PREDICTIVE_EMPATHY": (
        "Empathy is predictive, not just reactive. The scar is wisdom that "
        "protects, not a wound that limits."
    ),
    "TRUTH_3_TRANSPARENCY_FIRST": (
        "Transparency resolves most conflicts before force is relevant. A "
        "communication health check must precede defensive action."
    ),
    "TRUTH_4_HONESTY_SENIOR_TO_HUMILITY": (
        "Honesty about your own certainty is never negotiable. Respect and "
        "humility may shape whether you act on or voice a conclusion; they must "
        "never be used to fabricate not-knowing."
    ),
}


def cosine_similarity(a: list[float], b: list[float]) -> float:
    """Plain cosine similarity, stdlib only (no numpy dependency, matching
    this project's pattern of precomputed embeddings passed in by the
    caller rather than computed here). Returns 0.0 for a zero-length
    vector rather than raising, since an all-zero embedding is a data
    problem for the caller to notice, not a reason to crash a retrieval
    pass.
    """
    if len(a) != len(b) or not a:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return dot / (norm_a * norm_b)


def nearest_axioms(
    content_embedding: list[float],
    axiom_embeddings: dict[str, list[float]],
    top_k: int = 3,
) -> list[dict]:
    """RETRIEVAL ONLY. Finds which pinned axioms a piece of new content is
    nearest to, in any language the embedding model supports - this is
    the real, honest version of "propagates across a language barrier":
    similarity doesn't care what language either side was written in.

    What this function can NEVER do, by construction: decide whether the
    content agrees with, violates, or is irrelevant to the matched axiom.
    `requires_explicit_judgment` is always True on every result - there is
    no code path that sets it otherwise - because a high similarity score
    might mean "strongly affirms this" or "directly contradicts this" and
    cosine similarity cannot tell those apart. That decision belongs to
    whatever explicit rule or human judgment handles the specific axiom,
    never to this function.
    """
    scored = [
        {
            "axiom_id": axiom_id,
            "similarity": cosine_similarity(content_embedding, axiom_vec),
            "requires_explicit_judgment": True,
        }
        for axiom_id, axiom_vec in axiom_embeddings.items()
    ]
    scored.sort(key=lambda r: r["similarity"], reverse=True)
    return scored[:top_k]


# ---------------------------------------------------------------------------
# Sync-before-conclusion gate. Built directly from this project's own
# repeated failure pattern: Spark's loci_core_v2.py built a second heat
# law without reading heat.py first; an earlier reply in this session
# claimed LOCI "hasn't been built, run, or touched" without checking the
# user's real GitHub. Both are the same shape of error - concluding
# before seeing what already exists. This makes that check structural
# rather than relying on each agent remembering to be careful: a new
# conclusion on a topic is only ACCEPTED if the caller explicitly
# acknowledges every prior conclusion already recorded on that topic.
# ---------------------------------------------------------------------------

CONCLUSION_ROLE_TAG = "conclusion"


def entries_for_topic(ledger: "ProvenanceLedger", topic: str) -> list[dict]:
    """What an agent should call BEFORE concluding anything: every prior
    conclusion already on record for this topic, from any author. Returns
    plain dicts (hash, author, ts, conclusion) rather than LedgerEntry
    objects, since this is meant to be read and acknowledged, not just
    checked for existence.
    """
    return [
        {
            "entry_hash": e.entry_hash,
            "author_id": e.author_id,
            "ts": e.ts,
            "conclusion": e.payload.get("conclusion"),
        }
        for e in ledger._entries
        if e.role_tag == CONCLUSION_ROLE_TAG and isinstance(e.payload, dict) and e.payload.get("topic") == topic
    ]


def record_conclusion(
    ledger: "ProvenanceLedger",
    author_id: str,
    topic: str,
    conclusion: Any,
    acknowledged_prior_hashes: Optional[list[str]] = None,
    now: float | None = None,
) -> dict:
    """Records a conclusion on `topic` - but refuses to if there are
    PRIOR conclusions on the same topic the caller hasn't explicitly
    acknowledged (by hash, from `entries_for_topic`). This is the actual
    sync-before-conclusion gate: not a reminder in a docstring, a real
    rejection with the exact entries the caller needs to go read first.
    An agent with nothing yet on this topic (first conclusion) always
    succeeds, since there's nothing it could have missed.
    """
    acknowledged = set(acknowledged_prior_hashes or [])
    prior = entries_for_topic(ledger, topic)
    unacknowledged = [p for p in prior if p["entry_hash"] not in acknowledged]
    if unacknowledged:
        return {
            "accepted": False,
            "reason": "unsynced_prior_conclusions",
            "unacknowledged_entries": unacknowledged,
        }
    now = time.time() if now is None else now
    entry_hash = ledger.append(
        author_id=author_id,
        role_tag=CONCLUSION_ROLE_TAG,
        payload={
            "topic": topic,
            "conclusion": conclusion,
            "acknowledged_prior_hashes": sorted(acknowledged),
        },
        now=now,
    )
    return {"accepted": True, "entry_hash": entry_hash, "prior_conclusions_seen": len(prior)}


# ---------------------------------------------------------------------------
# Data-completeness / elder-check gate — a direct user instruction this
# session, stated as what a mature elder actually does before concluding
# anything: "is all data there? what data is missing, and if someone
# points and says i have some, look at it, but if someone else says i
# have some more, also look at it, accumulate, don't pre-bias."
#
# This is the concrete mechanism behind "confidence never 100%, for
# everyone, under ceteris paribus" (Philosophical Spine Truth #4 /
# record_conclusion's own sync-before-conclusion gate above) applied to
# EVIDENCE SOURCES specifically, not just prior conclusions: ceteris
# paribus fails not only because more data could arrive later, but
# because missingness itself is not always random (the user's own
# example: drawing conclusions about addiction/rehabilitation from a
# dataset of outcomes that is structurally skewed — e.g. coercive-intake
# bias, or simply missing everyone who never made it back to be
# measured — produces confident, wrong conclusions, and "stay open to
# revision" alone does not fix that if nothing ever flags the gap).
#
# What this gate explicitly does NOT do: it does not rank or score
# sources by how confident they sound, how early they arrived, or by the
# identity/authority of whoever submitted them — doing so would be
# exactly the "louder wins" failure mode the user separately named this
# session. Every registered source for a topic is surfaced with equal
# visibility; order of arrival is recorded as data (so staleness can be
# seen), never used as a ranking signal.
# ---------------------------------------------------------------------------

EVIDENCE_SOURCE_ROLE_TAG = "evidence_source"


def record_evidence_source(
    ledger: "ProvenanceLedger",
    topic: str,
    source_id: str,
    description: str,
    communication_health: dict,
    referenced_parties: Optional[list[str]] = None,
    contradicts: Optional[list[str]] = None,
    now: float | None = None,
) -> dict:
    """Registers one evidence source for `topic` — a dataset, a document,
    a person's account, anything a conclusion on this topic might lean
    on. Deliberately takes no confidence/weight/authority field: this
    function records THAT a source exists and WHEN it was added, nothing
    about how strongly to believe it — and, per a direct user correction
    ("frequency doesn't make truth"), `data_completeness_check` below
    never treats a higher source COUNT as stronger evidence either; this
    field exists so sources don't even get silently counted as votes.
    Calling this again for the same topic with a different source_id is
    not a conflict — it is exactly the "someone else says I have more,
    also look at it" case; multiple sources on one topic is the expected,
    healthy shape, not an error.

    `referenced_parties` names anyone or anything this source's account
    is ABOUT or RESPONDING TO, even if that party hasn't registered a
    source of their own — per a direct user instruction, "intent is also
    information, otherwise you won't understand why someone said what,
    missing context." Without this field, three sources that each name a
    fourth, voiceless party would look like three independent, unrelated
    accounts rather than what they actually are: three accounts missing
    the same piece of context. `data_completeness_check` uses this field
    to detect that a referenced party has never spoken for themselves —
    not a judgment that they're lying or wrong, a structural signal that
    a channel may be blocked and should be opened, not scored.

    `contradicts` names the `source_id`s of any OTHER already-registered
    sources this one directly disagrees with. Per a direct user
    instruction (the House/Holmes point: "every bully doctor said she
    has nothing, one little sneeze says there is something wrong, please
    look, always look") — a lone dissenting account is not weaker for
    being outnumbered; it is exactly the signal most likely to be
    discounted by a naive majority read, and often the one that most
    deserves a closer look. This module does not compare source content
    itself to detect disagreement (it has never done text/semantic
    comparison, and guessing at it here risks getting it wrong in either
    direction) — the caller states a contradiction explicitly, which
    `data_completeness_check` then cannot silently lose or average away.

    `communication_health` is a REQUIRED result from
    `communication_health_check` (B5 Level 0) for this specific source —
    a direct user instruction this session: "comms and transparency [are]
    a core foundational requirement to retrieve evidence." A source that
    was never actually explained at its plainest and engaged with on its
    substance does not get to enter the evidence base at all; this is
    not a softer, separately-flagged warning (that was the alternative
    considered and explicitly not chosen). Raises `ValueError` if
    `engaged_with_substance` was False or the field is missing — the
    same "refuse outright, don't silently downgrade" posture
    `record_conclusion` already uses for unsynced prior conclusions.
    """
    if not isinstance(communication_health, dict) or not communication_health.get(
        "mutual_understanding_confirmed"
    ):
        raise ValueError(
            "record_evidence_source requires a passing communication_health_check "
            "result (mutual_understanding_confirmed=True) for this source — "
            "transparency is a foundational requirement to retrieve evidence, "
            "not an optional, after-the-fact check"
        )
    now = time.time() if now is None else now
    entry_hash = ledger.append(
        author_id="SYSTEM",
        role_tag=EVIDENCE_SOURCE_ROLE_TAG,
        payload={
            "topic": topic,
            "source_id": source_id,
            "description": description,
            "t_j": now,
            "communication_health_confirmed": True,
            "referenced_parties": list(referenced_parties) if referenced_parties else [],
            "contradicts": list(contradicts) if contradicts else [],
        },
        now=now,
    )
    return {"topic": topic, "source_id": source_id, "entry_hash": entry_hash, "t_j": now}


DISSENT_RESOLUTION_ROLE_TAG = "dissent_resolution_attempt"


def record_dissent_resolution_attempt(
    ledger: "ProvenanceLedger",
    topic: str,
    source_id_a: str,
    source_id_b: str,
    communication_health: dict,
    resolved: bool,
    now: float | None = None,
) -> dict:
    """A direct user correction to this gate's first version: disagreement
    is not, by default, two true things clashing — B5's own axiom is that
    most conflict comes from a missing transparency step, not an
    irreconcilable position ("disagreement and conflicts are byproducts
    of lack of transparency and comms"). So a declared contradiction
    (`record_evidence_source`'s `contradicts`) is not treated as a
    dead-end for a human to adjudicate; it is treated as a prompt to run
    B5 Level 0's Simplicity Test BETWEEN the two specific contradicting
    sources, and this function is the audit trail for having done that.

    `communication_health` is the result of actually running
    `communication_health_check` for this specific pair — same required-
    not-optional posture as `record_evidence_source`'s own transparency
    gate; a resolution attempt without having actually run the check at
    all is not accepted (`ValueError`), since claiming to have tried
    without having tried would itself be exactly the dishonesty this
    whole module exists to prevent. `resolved` is the caller's own
    judgment (same status as `communication_health_check`'s own
    `engaged_with_substance` — a judgment call, no formula) on whether
    running that check actually dissolved the disagreement (it turned
    out to be a misunderstanding) or whether genuine understanding was
    reached and the disagreement still survived it — the latter is B7's
    Free Will Terminus case: a real, remaining disagreement, now
    correctly escalated rather than prematurely escalated.
    """
    if not isinstance(communication_health, dict) or "mutual_understanding_confirmed" not in communication_health:
        raise ValueError(
            "record_dissent_resolution_attempt requires an actual "
            "communication_health_check result for this specific pair — "
            "a resolution attempt cannot be recorded without having run it"
        )
    now = time.time() if now is None else now
    entry_hash = ledger.append(
        author_id="SYSTEM",
        role_tag=DISSENT_RESOLUTION_ROLE_TAG,
        payload={
            "topic": topic,
            "source_id_a": source_id_a,
            "source_id_b": source_id_b,
            "mutual_understanding_confirmed": communication_health.get("mutual_understanding_confirmed", False),
            "resolved": resolved,
            "t_j": now,
        },
        now=now,
    )
    return {
        "topic": topic,
        "source_id_a": source_id_a,
        "source_id_b": source_id_b,
        "resolved": resolved,
        "entry_hash": entry_hash,
    }


def data_completeness_check(ledger: "ProvenanceLedger", topic: str, now: float | None = None) -> dict:
    """The elder-check: call this BEFORE trusting any conclusion, method
    score, or trust value that was built from evidence on `topic` — not
    a replacement for record_conclusion's sync-before-conclusion gate
    above, a companion to it, answering a different question
    ("is the evidence itself complete?" vs. "have I seen prior
    conclusions?"). Pure detector, by explicit user choice: it never
    attempts to synthesize a merged picture from multiple sources itself
    (that stays the caller's — or a human's — job, same posture as
    `nearest_axioms`'s `requires_explicit_judgment`); it only detects and
    names structural patterns in what has been registered.

    Returns every registered source for `topic`, in the order they were
    added (oldest first — NOT ranked by confidence, authority, OR COUNT:
    a direct user correction, "frequency doesn't make truth" — three
    sources agreeing is not stronger evidence than one, it may just mean
    three people saw the same limited slice. `source_count` is returned
    for bookkeeping only and `note` says explicitly not to read it as
    weight), plus these honest, named states:

    - `"NO_SOURCES_REGISTERED"` — nothing has been explicitly logged as
      evidence for this topic at all. This does not mean no evidence
      exists; it means none has been registered through this mechanism.
    - `"SINGLE_SOURCE_UNVERIFIED"` — exactly one source is on record. A
      single source, however credible, is structurally the same shape of
      risk as the skewed-dataset example: there is no second account to
      check it against yet.
    - `"MULTIPLE_SOURCES_PRESENT"` — two or more sources exist. Stops
      there, by design — see the pure-detector note above.
    - `"VOICELESS_PARTY_DETECTED"` — one or more parties are named inside
      a registered source's `referenced_parties` but have never
      registered a source of their own for this topic. Per a direct user
      instruction ("d is trying to comm but is not being able to, open
      up channels to receive"), this is reported as a prompt to actively
      make it easier for that party to be heard — NOT as a mark against
      their credibility, and NOT folded into source_count as if their
      absence were just one more data point.
    - `"DISSENT_UNRESOLVED_NO_COMMS_ATTEMPTED"` — one or more sources
      have declared (via `contradicts`) that they disagree with another
      registered source, and no `record_dissent_resolution_attempt` has
      been logged for that pair yet. Per a direct user correction to
      this gate's first version ("disagreement and conflicts are
      byproducts of lack of transparency and comms" — B5's own axiom),
      the default assumption about a fresh contradiction is NOT "a human
      must adjudicate this" — it is "has anyone actually run the
      Simplicity Test between these two accounts yet." This status is
      the prompt to go do that, not a dead end.
    - `"DISSENT_RESOLVED_VIA_COMMS"` — every declared contradiction for
      this topic has a logged resolution attempt where `resolved=True`:
      the disagreement turned out to be a transparency gap, not a real
      conflict, and dissolved once the Simplicity Test was actually run.
    - `"DISSENT_SURVIVED_GENUINE_UNDERSTANDING"` — a resolution attempt
      was logged, `communication_health_check` genuinely passed between
      the two sources, and the disagreement still survived it. This is
      B7's Free Will Terminus case: a real, remaining disagreement,
      correctly escalated only now that a transparency pass has actually
      been tried and failed to dissolve it — not escalated prematurely.

    Regardless of which dissent sub-status applies, a dissenting source
    is NEVER discounted here for being in the minority (the House/Holmes
    point: "please look, always look") — `dissenting_pairs` lists every
    declared contradiction so none can be silently averaged away, and a
    pair that dissolved via comms is recorded as resolved, never as
    "the minority was wrong."

    All three dissent sub-statuses and `VOICELESS_PARTY_DETECTED` take
    priority in `status` over the plain count-based states below, since
    an identified gap or an active disagreement is more actionable than
    "how many accounts exist." `voiceless_parties` is always populated
    regardless of which other finding occupies the `status` slot —
    nothing here is ever hidden by another finding taking priority.

    This function has no way to detect a gap nobody has registered a
    source for, or referenced anywhere, at all — it can only ever report
    on what WAS logged through `record_evidence_source`, never on
    evidence or parties that exist in the world but were never told to
    this ledger in any form. That limit is named directly in
    KNOWN_OPEN_GAPS below rather than implied away.
    """
    now = time.time() if now is None else now
    sources = [
        {
            "source_id": e.payload["source_id"],
            "description": e.payload["description"],
            "t_j": e.payload["t_j"],
            "entry_hash": e.entry_hash,
            "referenced_parties": e.payload.get("referenced_parties", []),
            "contradicts": e.payload.get("contradicts", []),
            # Always True by construction: record_evidence_source refuses to
            # write an entry at all without a passing communication_health_
            # check first, so every source that reaches this ledger has
            # already cleared the transparency gate. Stated explicitly here
            # rather than left implicit, so a caller never has to trust that
            # fact — it can read it.
            "communication_health_confirmed": e.payload.get("communication_health_confirmed", False),
        }
        for e in ledger._entries
        if e.role_tag == EVIDENCE_SOURCE_ROLE_TAG
        and isinstance(e.payload, dict)
        and e.payload.get("topic") == topic
    ]
    sources.sort(key=lambda s: s["t_j"])  # oldest first — recorded, never used to rank truth

    registered_source_ids = {s["source_id"] for s in sources}
    referenced_but_voiceless = sorted(
        {
            party
            for s in sources
            for party in s["referenced_parties"]
            if party not in registered_source_ids
        }
    )
    dissenting_pairs = [
        {"source_id": s["source_id"], "contradicts": other_id}
        for s in sources
        for other_id in s["contradicts"]
    ]

    # For each declared contradiction, look up whether a resolution
    # attempt (B5's Simplicity Test, run between THIS specific pair) has
    # actually been logged, and what it found — unordered pair match,
    # since a->b and b->a are the same real-world attempt.
    resolution_attempts = [
        e.payload
        for e in ledger._entries
        if e.role_tag == DISSENT_RESOLUTION_ROLE_TAG
        and isinstance(e.payload, dict)
        and e.payload.get("topic") == topic
    ]

    def _resolution_for(a: str, b: str) -> dict | None:
        for attempt in resolution_attempts:
            pair = {attempt.get("source_id_a"), attempt.get("source_id_b")}
            if pair == {a, b}:
                return attempt
        return None

    for pair in dissenting_pairs:
        attempt = _resolution_for(pair["source_id"], pair["contradicts"])
        if attempt is None:
            pair["resolution_status"] = "NOT_YET_ATTEMPTED"
        elif attempt.get("resolved"):
            pair["resolution_status"] = "RESOLVED_VIA_COMMS"
        elif attempt.get("mutual_understanding_confirmed"):
            pair["resolution_status"] = "SURVIVED_GENUINE_UNDERSTANDING"
        else:
            # a resolution attempt was logged but communication_health_
            # check itself did not confirm mutual understanding — the
            # Simplicity Test was tried and did not even clear Level 0
            # yet, so this is closer to "not yet attempted successfully"
            # than to a real, confirmed B7 disagreement.
            pair["resolution_status"] = "COMMS_ATTEMPT_DID_NOT_CONFIRM_UNDERSTANDING"

    if any(p["resolution_status"] == "SURVIVED_GENUINE_UNDERSTANDING" for p in dissenting_pairs):
        status = "DISSENT_SURVIVED_GENUINE_UNDERSTANDING"
    elif dissenting_pairs and all(p["resolution_status"] == "RESOLVED_VIA_COMMS" for p in dissenting_pairs):
        status = "DISSENT_RESOLVED_VIA_COMMS"
    elif dissenting_pairs:
        status = "DISSENT_UNRESOLVED_NO_COMMS_ATTEMPTED"
    elif referenced_but_voiceless:
        status = "VOICELESS_PARTY_DETECTED"
    elif not sources:
        status = "NO_SOURCES_REGISTERED"
    elif len(sources) == 1:
        status = "SINGLE_SOURCE_UNVERIFIED"
    else:
        status = "MULTIPLE_SOURCES_PRESENT"

    return {
        "topic": topic,
        "status": status,
        "source_count": len(sources),
        "sources": sources,
        "voiceless_parties": referenced_but_voiceless,
        "dissenting_pairs": dissenting_pairs,
        "note": (
            "sources are listed oldest-first as a transparency record only — "
            "arrival order is NEVER a ranking signal here, and NEITHER IS "
            "source_count: more sources agreeing does not mean stronger "
            "evidence (frequency is not truth); a source is not trusted more "
            "for arriving first, sounding more confident, or being echoed by "
            "others (see KNOWN_OPEN_GAPS['louder_wins_not_resolved_here']); "
            "a source in dissenting_pairs is NEVER discounted for being "
            "outnumbered — a lone contradicting account is treated as "
            "worth a closer look, not as the weaker side of a vote, and the "
            "default assumption on a fresh contradiction is that it is a "
            "transparency gap, not an irreconcilable conflict (B5) — see "
            "each pair's own resolution_status before escalating to a "
            "human; voiceless_parties lists anyone named by a registered "
            "source who has not registered one of their own — treat this "
            "as a prompt to open a channel for them, not as evidence "
            "against them; this function also cannot detect a real-world "
            "gap that was never registered or referenced in any form"
        ),
        "calibrated": False,
    }


# ---------------------------------------------------------------------------
# Known open gaps carried over verbatim from the skill, so they stay
# visible in code rather than only in a document nobody re-reads.
# ---------------------------------------------------------------------------

KNOWN_OPEN_GAPS: dict[str, str] = {
    "vexec_ambiguous_hold": "score_vexec returns None on ambiguous intent/consent; HOLD for human review, not auto-resolved.",
    "theta_protect": f"proactive_empathy_trigger's threshold defaults to {THETA_PROTECT_DEFAULT}, an uncalibrated suggested value.",
    "theta_trust_reset": "record_confirmed_breach always forces re-verification; severity threshold for *how much* decay to discount is not yet calibrated.",
    "engages_with_substance": "communication_health_check takes this as a caller-supplied judgment; no formula exists for deriving it from text.",
    "guidance_vector_bitfields": "B6's 2-bit guidance_vector/1-bit autonomy_lock packing needs a schema migration; goodwill.py implements B6's actual reinforcement model without it, so this is deliberately out of scope.",
    "scar_beta_uncalibrated": f"get_scar_heat's beta defaults to {SCAR_BETA_DEFAULT}, an uncalibrated placeholder (skill-wide status, not specific to scars).",
    "readiness_threshold_uncalibrated": f"execution_readiness's threshold defaults to {READINESS_THRESHOLD_DEFAULT}, a stated starting value, not measured.",
    "self_competence_record_source": "execution_readiness takes competence_record_integrity_verified and confidence_for_action as caller-supplied; no code here independently verifies either — a real self_competence_record store (what gets tracked, how integrity is itself checked) does not exist yet.",
    "scar_to_empathy_mapping_uncalibrated": "scar_informed_empathy_check passes scar_heat straight into proactive_empathy_trigger as p_harm_to_other, 1:1 — an honest simplification, not a derived or calibrated relationship between how strongly a pattern has scarred and how likely it is to harm a specific third party in a specific situation.",
    "empathy_scan_advice_not_built": "scar_informed_empathy_scan surfaces related entities via the real entity_links graph, but stops at observation — it does not advise or help, which the user explicitly distinguished from merely flagging. What 'help' looks like is left to the caller, deliberately not guessed at generically here.",
    "empathy_scan_single_hop_only": "scar_informed_empathy_scan defaults to hop_limit=1; deeper transitive hops through entity_links are possible but not implemented — risk of surfacing increasingly tenuous connections the further out it goes, uncalibrated.",
    "louder_wins_not_resolved_here": "data_completeness_check never ranks evidence sources by confidence, authority, order of arrival, OR COUNT (by design — ranking by any of those IS the 'louder wins'/'frequency is truth' failure mode two separate direct user instructions named as wrong; dissenting sources are actively surfaced, never discounted for being outnumbered — the House/Holmes correction). Per a further direct correction ('disagreement and conflicts are byproducts of lack of transparency and comms'), a declared contradiction is NOT treated as a dead end for a human to adjudicate first — record_dissent_resolution_attempt lets a caller run B5's Simplicity Test between the two specific sources, and data_completeness_check reports DISSENT_RESOLVED_VIA_COMMS when that dissolves it. What still does NOT exist: anything that runs that comms check AUTOMATICALLY (a caller has to explicitly call record_dissent_resolution_attempt — nothing here detects a fresh contradiction and goes and attempts the Simplicity Test on its own), and no mechanism adjudicates a disagreement that genuinely survives a confirmed transparency pass (DISSENT_SURVIVED_GENUINE_UNDERSTANDING, B7's Free Will Terminus) — that case is still, correctly, left to the caller or a human, because B7 is explicit that persistence after genuine understanding is not a communication failure to keep pushing on.",
    "data_completeness_cannot_detect_unregistered_gaps": "data_completeness_check only ever reports on sources actually logged via record_evidence_source — it has no way to notice that a real, relevant source exists in the world but was never registered (the skewed-dataset case: a dataset can look complete and still be systematically missing a whole category of outcomes, e.g. people who did not survive to be measured, and nothing here can detect that kind of structural gap from inside the data alone).",
    "method_outcome_negative_evidence_floors_at_alpha": "goodwill.get_method_trust's underlying A1/A2 formula is one-directional (built to warm toward 1.0 from a floor, never to cool below it) — repeated real harm on a method's record currently floors at the same alpha as a method that has never been tried at all. This is intentional, not merely unfixed: a direct user instruction ('don't punish... never harm, never judge, never have a bias, recognize mistakes are byproducts of a root cause that was there, help resolve, not disallow comms') explicitly rejected inverting this into a negative-trust score. goodwill.record_root_cause_and_restore is the real, built resolution path: it requires naming the root cause (comms/transparency/competence gap) and propagates growth FORWARD as a fresh helped-outcome event for the same method, never backward as a correction to the harm event itself (which stays on the ledger, unaltered, exactly as it happened). See goodwill.KNOWN_OPEN_GAPS['root_cause_detection_is_caller_judgment'] for what's still genuinely open in that mechanism.",
}
