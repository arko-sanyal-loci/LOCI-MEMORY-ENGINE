#!/usr/bin/env python3
"""
loci_engine/store.py
=====================
Entity-level persistence for anything whose heat needs tracking over time:
trust patterns, scar-adjacent entities, and any other named thing that
accumulates evidence rather than holding a single mutable score.

This sits directly on top of storage.py's context2.db — same schema, same
DDL, same memory_item table. It does not define a parallel storage
concept; an "entity" tracked here IS a memory_item row (item_type =
'observation', namespace = 'entity_trust'), consistent with how every
other kind of LOCI memory is stored.

HEAT IS ALWAYS RE-DERIVED, NEVER STORED AS A MUTABLE SCALAR
--------------------------------------------------------------
This is the same discipline ethics.py uses for scar heat (see
get_scar_heat() there): an entity's current heat is never written directly.
Instead, each touch_entity() call appends a timestamped evidence event to
the entity's event log (held in metadata_json), and heat is recomputed
fresh from the *full* event history via heat.evidence_accumulation() /
heat.evidence_heat() every time it's read. A single mutable "heat" column
updated by increment would let drift accumulate between the stored value
and what the open-interval law actually says it should be; re-deriving it
every time makes that impossible by construction.

The memory_item.heat column still gets written on every touch, but only
as a cached, always-fresh snapshot of the re-derived value — never as the
source of truth.
"""

from __future__ import annotations

import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loci_engine.heat import MEMORY_CLASSES, evidence_accumulation, evidence_heat
from loci_engine.storage import DB_PATH, DDL_SCHEMA

# Entities tracked by this module live in their own namespace, alongside
# (not instead of) facts, decisions, and the other item_types memory_item
# already supports.
ENTITY_NAMESPACE = "entity_trust"
_ENTITY_MEMORY_CLASS = MEMORY_CLASSES["valued_skill"]  # tau=20d, alpha=0.08


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _content_hash(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def open_db(path: Optional[str] = None) -> sqlite3.Connection:
    """Open the shared context2.db, initialising the schema if needed.

    Uses the exact same DDL as StorageEngine — this is the same database,
    not a second one. Call sites that already hold a connection (e.g. from
    a StorageEngine instance) can pass it directly to the functions below
    instead of calling this.
    """
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(DDL_SCHEMA)
    return conn


def _load_events(row: sqlite3.Row) -> List[tuple]:
    meta = json.loads(row["metadata_json"] or "{}")
    return [tuple(e) for e in meta.get("events", [])]


def _save_events(conn: sqlite3.Connection, entity_id: str, events: List[tuple], heat: float, now_iso: str) -> None:
    conn.execute(
        "UPDATE memory_item SET metadata_json = ?, heat = ?, last_observed_at = ?, updated_at = ? "
        "WHERE id = ? AND namespace = ?",
        (json.dumps({"events": events}), heat, now_iso, now_iso, entity_id, ENTITY_NAMESPACE),
    )
    conn.commit()


def get_entity(
    conn: sqlite3.Connection,
    entity_id: str,
    *,
    now: Optional[float] = None,
) -> Optional[Dict[str, Any]]:
    """Return an entity's current record, with heat re-derived fresh from
    its full event history — never the last-cached column value.

    Returns None if the entity doesn't exist or isn't active.
    """
    row = conn.execute(
        "SELECT * FROM memory_item WHERE id = ? AND namespace = ? AND status = 'active'",
        (entity_id, ENTITY_NAMESPACE),
    ).fetchone()
    if row is None:
        return None

    events = _load_events(row)
    import time as _time

    now_ts = now if now is not None else _time.time()
    evidence = evidence_accumulation(events, now=now_ts, tau=_ENTITY_MEMORY_CLASS.tau_days)
    heat = evidence_heat(evidence, alpha=_ENTITY_MEMORY_CLASS.alpha)

    record = dict(row)
    record["heat"] = heat
    record["event_count"] = len(events)
    return record


def remember_entity(
    conn: sqlite3.Connection,
    entity_id: str,
    *,
    gist: str = "",
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """Register a new entity. Idempotent — returns the existing record if
    one is already active under this id.
    """
    existing = get_entity(conn, entity_id, now=now)
    if existing is not None:
        return existing

    ts = _now_iso()
    alpha = _ENTITY_MEMORY_CLASS.alpha

    conn.execute(
        """INSERT INTO memory_item
           (id, namespace, item_type, canonical_text, lexical_text,
            source_event_id, source_actor, source_trust, confidence,
            sensitivity, era, alpha, heat, last_observed_at, valid_from,
            status, content_hash, created_at, updated_at, metadata_json)
           VALUES (?, ?, 'observation', ?, ?, ?, 'entity_store', 0.8, 0.5,
                   'internal', 'near', ?, ?, ?, ?, 'active', ?, ?, ?, ?)
        """,
        (
            entity_id, ENTITY_NAMESPACE, gist, gist.lower(),
            str(uuid.uuid4()), alpha, alpha + 1e-9,
            ts, ts, _content_hash(gist or entity_id), ts, ts,
            json.dumps({"events": []}),
        ),
    )
    conn.commit()
    return get_entity(conn, entity_id, now=now)  # type: ignore[return-value]


def touch_entity(
    conn: sqlite3.Connection,
    entity_id: str,
    *,
    hop: float = 0.05,
    now: Optional[float] = None,
) -> float:
    """Reinforce an entity with one new evidence event, and return its
    freshly re-derived heat.

    ``hop`` is the event's valence weight (relevance is fixed at 1.0) —
    appended to the entity's event log, not applied as a direct heat
    increment. The next get_entity()/touch_entity() call re-derives heat
    from the complete history via the A1/A2 law, exactly like scar heat.
    """
    import time as _time

    now_ts = now if now is not None else _time.time()

    row = conn.execute(
        "SELECT * FROM memory_item WHERE id = ? AND namespace = ? AND status = 'active'",
        (entity_id, ENTITY_NAMESPACE),
    ).fetchone()
    if row is None:
        raise KeyError(f"Entity {entity_id!r} not found — call remember_entity first")

    events = _load_events(row)
    events.append((now_ts, 1.0, hop))

    evidence = evidence_accumulation(events, now=now_ts, tau=_ENTITY_MEMORY_CLASS.tau_days)
    heat = evidence_heat(evidence, alpha=_ENTITY_MEMORY_CLASS.alpha)

    _save_events(conn, entity_id, events, heat, _now_iso())
    return heat
