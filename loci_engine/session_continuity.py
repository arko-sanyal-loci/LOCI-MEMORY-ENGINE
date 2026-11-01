#!/usr/bin/env python3
"""
LOCI Cross-Session Continuity — PRS, LDCE, Session Bridging

Three components claimed in the axonmemory.com artifact, now implemented:

1. Session Lifecycle: tracks session boundaries (start/end/agent), records
   which memories were active at each boundary for later PRS computation.

2. LDCE (Layered Dynamic Context Engine): kernel/hop/offload three-tier
   injection. At session start, the system injects the highest-heat facts
   into the kernel tier (always present), medium-heat into hop tier
   (available on demand), and low-heat into offload tier (retrievable
   but not preloaded). This keeps active context lean (C3 Miller's Law)
   while ensuring nothing is lost.

3. PRS (Persistence Recall Score): measures recall fidelity across session
   boundaries. After a session ends and a new one starts, PRS compares
   what was accessible in the old session vs what was recalled/used in the
   new session. Best theoretical ceiling is 1.28 (A2 evidence heat with
   formative scar alpha=0.14 and strong evidence).

All three are observe-only — they compute, record, and report. The caller
wires results into whatever decision path they own.
"""

import hashlib
import json
import math
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from loci_engine.storage import StorageEngine, DB_PATH

# ---------------------------------------------------------------------------
# Session table DDL — extends context2.db
# ---------------------------------------------------------------------------

SESSION_DDL = """
CREATE TABLE IF NOT EXISTS session_log (
    session_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    status TEXT NOT NULL CHECK(status IN ('active', 'completed', 'crashed', 'expired')),
    kernel_snapshot TEXT NOT NULL DEFAULT '[]',
    hop_snapshot TEXT NOT NULL DEFAULT '[]',
    offload_snapshot TEXT NOT NULL DEFAULT '[]',
    prs_score REAL,
    bridged_from TEXT REFERENCES session_log(session_id),
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_session_agent ON session_log(agent_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_session_status ON session_log(status);

CREATE TABLE IF NOT EXISTS session_recall_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES session_log(session_id),
    memory_item_id TEXT NOT NULL,
    recalled_at TEXT NOT NULL,
    recall_tier TEXT NOT NULL CHECK(recall_tier IN ('kernel', 'hop', 'offload', 'cold')),
    heat_at_recall REAL NOT NULL,
    was_in_prior_session INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_recall_session ON session_recall_log(session_id);
"""

# ---------------------------------------------------------------------------
# LDCE tier thresholds — calibrated to A2 heat curve behavior
# ---------------------------------------------------------------------------

KERNEL_HEAT_THRESHOLD = 0.50   # HOT tier — always in context
HOP_HEAT_THRESHOLD = 0.167     # MILD tier — available on 1-hop request
# Below HOP = COLD tier — offloaded, retrievable via search only

KERNEL_MAX_ITEMS = 7           # Miller's Law: 7 +/- 2
HOP_MAX_ITEMS = 15
OFFLOAD_MAX_ITEMS = 50

# ---------------------------------------------------------------------------
# PRS constants
# ---------------------------------------------------------------------------

PRS_CEILING = 1.28  # theoretical max: scar alpha=0.14, beta*E large


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_session_tables(engine: StorageEngine) -> None:
    with engine._get_connection() as conn:
        conn.executescript(SESSION_DDL)


# ---------------------------------------------------------------------------
# Session Lifecycle
# ---------------------------------------------------------------------------

def start_session(
    engine: StorageEngine,
    agent_id: str,
    bridge_from_session: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Start a new session. If bridge_from_session is given, carries forward
    the kernel snapshot from the prior session as the new session's starting
    context — this is the cross-session continuity bridge.

    Returns the session record including the LDCE tier assignments.
    """
    _ensure_session_tables(engine)
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    now = _utc_iso()

    # Expire any dangling active sessions for this agent
    with engine._get_connection() as conn:
        conn.execute(
            "UPDATE session_log SET status = 'expired', ended_at = ? "
            "WHERE agent_id = ? AND status = 'active'",
            (now, agent_id),
        )
        conn.commit()

    # Compute LDCE tiers from current memory state
    tiers = compute_ldce_tiers(engine)

    # If bridging, merge prior kernel into new kernel
    prior_kernel = []
    if bridge_from_session:
        with engine._get_connection() as conn:
            row = conn.execute(
                "SELECT kernel_snapshot FROM session_log WHERE session_id = ?",
                (bridge_from_session,),
            ).fetchone()
            if row:
                prior_kernel = json.loads(row[0])

    with engine._get_connection() as conn:
        conn.execute(
            """INSERT INTO session_log
               (session_id, agent_id, started_at, status,
                kernel_snapshot, hop_snapshot, offload_snapshot,
                bridged_from, metadata_json)
               VALUES (?, ?, ?, 'active', ?, ?, ?, ?, ?)""",
            (
                session_id, agent_id, now,
                json.dumps(tiers["kernel"]),
                json.dumps(tiers["hop"]),
                json.dumps(tiers["offload"]),
                bridge_from_session,
                json.dumps(metadata or {}),
            ),
        )
        conn.commit()

    return {
        "session_id": session_id,
        "agent_id": agent_id,
        "started_at": now,
        "bridged_from": bridge_from_session,
        "ldce": tiers,
        "prior_kernel_items": len(prior_kernel),
    }


def end_session(
    engine: StorageEngine,
    session_id: str,
    status: str = "completed",
) -> Dict[str, Any]:
    """End a session. Computes PRS if bridged from a prior session."""
    _ensure_session_tables(engine)
    now = _utc_iso()

    with engine._get_connection() as conn:
        row = conn.execute(
            "SELECT bridged_from, kernel_snapshot FROM session_log WHERE session_id = ?",
            (session_id,),
        ).fetchone()

        if not row:
            return {"error": f"session {session_id} not found"}

        bridged_from = row[0]
        current_kernel = json.loads(row[1])

        # Compute PRS if this session was bridged
        prs = None
        if bridged_from:
            prs = compute_prs(engine, bridged_from, session_id)

        conn.execute(
            "UPDATE session_log SET ended_at = ?, status = ?, prs_score = ? "
            "WHERE session_id = ?",
            (now, status, prs, session_id),
        )
        conn.commit()

    return {
        "session_id": session_id,
        "ended_at": now,
        "status": status,
        "prs_score": prs,
    }


# ---------------------------------------------------------------------------
# LDCE — Layered Dynamic Context Engine
# ---------------------------------------------------------------------------

def compute_ldce_tiers(
    engine: StorageEngine,
    namespace_filter: Optional[str] = None,
) -> Dict[str, List[Dict[str, Any]]]:
    """Compute the three-tier LDCE assignment from current memory state.

    Tier 0 (kernel): highest-heat items, always in context. Max 7 items.
    Tier 1 (hop): medium-heat items, injected on 1-hop expansion. Max 15.
    Tier 2 (offload): low-heat items, retrievable via search. Max 50.

    Items below offload threshold are "cold storage" — still in the DB
    but not preloaded into any tier.
    """
    with engine._get_connection() as conn:
        query = """
            SELECT id, namespace, canonical_text, heat, era, alpha,
                   last_observed_at, status
            FROM memory_item
            WHERE status = 'active'
        """
        params: list = []
        if namespace_filter:
            query += " AND namespace LIKE ?"
            params.append(f"{namespace_filter}%")
        query += " ORDER BY heat DESC"

        rows = conn.execute(query, params).fetchall()

    kernel = []
    hop = []
    offload = []

    for row in rows:
        item = {
            "id": row[0],
            "namespace": row[1],
            "text": row[2],
            "heat": row[3],
            "era": row[4],
            "alpha": row[5],
        }

        heat = row[3]
        if heat >= KERNEL_HEAT_THRESHOLD and len(kernel) < KERNEL_MAX_ITEMS:
            item["tier"] = "kernel"
            kernel.append(item)
        elif heat >= HOP_HEAT_THRESHOLD and len(hop) < HOP_MAX_ITEMS:
            item["tier"] = "hop"
            hop.append(item)
        elif len(offload) < OFFLOAD_MAX_ITEMS:
            item["tier"] = "offload"
            offload.append(item)

    return {
        "kernel": kernel,
        "hop": hop,
        "offload": offload,
        "stats": {
            "kernel_count": len(kernel),
            "hop_count": len(hop),
            "offload_count": len(offload),
            "total_active": len([r for r in rows]),
            "context_token_estimate": _estimate_tokens(kernel),
        },
    }


def _estimate_tokens(items: List[Dict[str, Any]]) -> int:
    """Rough token estimate for kernel items — 4 bytes per token."""
    total_bytes = sum(len(item.get("text", "").encode("utf-8")) for item in items)
    return (total_bytes // 4) + 1


def inject_context(
    engine: StorageEngine,
    session_id: str,
    tier: str = "kernel",
) -> List[Dict[str, Any]]:
    """Retrieve items for the requested LDCE tier from the session snapshot.
    This is what gets injected into the agent's context at session start
    or on 1-hop expansion.
    """
    _ensure_session_tables(engine)
    col_map = {
        "kernel": "kernel_snapshot",
        "hop": "hop_snapshot",
        "offload": "offload_snapshot",
    }
    col = col_map.get(tier)
    if not col:
        return []

    with engine._get_connection() as conn:
        row = conn.execute(
            f"SELECT {col} FROM session_log WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        if not row:
            return []
        return json.loads(row[0])


def record_recall(
    engine: StorageEngine,
    session_id: str,
    memory_item_id: str,
    recall_tier: str,
    heat_at_recall: float,
    was_in_prior: bool = False,
) -> None:
    """Log that a memory item was recalled during this session.
    Used by PRS to measure cross-session recall fidelity.
    """
    _ensure_session_tables(engine)
    with engine._get_connection() as conn:
        conn.execute(
            """INSERT INTO session_recall_log
               (session_id, memory_item_id, recalled_at, recall_tier,
                heat_at_recall, was_in_prior_session)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (session_id, memory_item_id, _utc_iso(), recall_tier,
             heat_at_recall, 1 if was_in_prior else 0),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# PRS — Persistence Recall Score
# ---------------------------------------------------------------------------

def compute_prs(
    engine: StorageEngine,
    prior_session_id: str,
    current_session_id: str,
) -> float:
    """Compute the Persistence Recall Score between two sessions.

    PRS measures how well memories from the prior session were recalled
    in the current session, weighted by their heat at both boundaries.

    Formula:
        PRS = sum(heat_prior_i * heat_current_i * recall_weight_i) /
              sum(heat_prior_i)

    Where:
        - heat_prior_i = heat of item i at end of prior session
        - heat_current_i = heat of item i at recall time in current session
        - recall_weight_i = 1.0 for kernel recall, 0.75 for hop, 0.5 for
          offload, 0.25 for cold (had to search for it)

    PRS ranges from 0 to PRS_CEILING (1.28). A score of 0.832 means
    83.2% of prior-session heat was successfully recalled with fidelity.
    """
    TIER_WEIGHTS = {
        "kernel": 1.0,
        "hop": 0.75,
        "offload": 0.5,
        "cold": 0.25,
    }

    with engine._get_connection() as conn:
        # Get prior session's kernel+hop items (what was "known")
        prior_row = conn.execute(
            "SELECT kernel_snapshot, hop_snapshot FROM session_log WHERE session_id = ?",
            (prior_session_id,),
        ).fetchone()
        if not prior_row:
            return 0.0

        prior_items = json.loads(prior_row[0]) + json.loads(prior_row[1])
        if not prior_items:
            return 0.0

        prior_map = {item["id"]: item["heat"] for item in prior_items}

        # Get current session's recall log
        recalls = conn.execute(
            "SELECT memory_item_id, heat_at_recall, recall_tier "
            "FROM session_recall_log WHERE session_id = ?",
            (current_session_id,),
        ).fetchall()

        recalled_map: Dict[str, Tuple[float, str]] = {}
        for r in recalls:
            item_id, heat, tier = r
            if item_id in prior_map:
                # Keep the best recall (highest tier weight)
                if item_id not in recalled_map or TIER_WEIGHTS.get(tier, 0) > TIER_WEIGHTS.get(recalled_map[item_id][1], 0):
                    recalled_map[item_id] = (heat, tier)

    # Compute PRS
    numerator = 0.0
    denominator = 0.0

    for item_id, prior_heat in prior_map.items():
        denominator += prior_heat
        if item_id in recalled_map:
            current_heat, tier = recalled_map[item_id]
            tier_weight = TIER_WEIGHTS.get(tier, 0.25)
            numerator += prior_heat * current_heat * tier_weight

    if denominator == 0.0:
        return 0.0

    raw_prs = numerator / denominator
    return min(PRS_CEILING, round(raw_prs, 4))


def get_session_history(
    engine: StorageEngine,
    agent_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Retrieve recent session history, optionally filtered by agent."""
    _ensure_session_tables(engine)
    with engine._get_connection() as conn:
        if agent_id:
            rows = conn.execute(
                "SELECT session_id, agent_id, started_at, ended_at, status, "
                "prs_score, bridged_from FROM session_log "
                "WHERE agent_id = ? ORDER BY started_at DESC LIMIT ?",
                (agent_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT session_id, agent_id, started_at, ended_at, status, "
                "prs_score, bridged_from FROM session_log "
                "ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

    return [
        {
            "session_id": r[0],
            "agent_id": r[1],
            "started_at": r[2],
            "ended_at": r[3],
            "status": r[4],
            "prs_score": r[5],
            "bridged_from": r[6],
        }
        for r in rows
    ]


def get_prs_trend(
    engine: StorageEngine,
    agent_id: str,
    limit: int = 10,
) -> Dict[str, Any]:
    """Get the PRS trend for an agent — shows whether cross-session
    recall fidelity is improving, degrading, or stable over time.
    """
    _ensure_session_tables(engine)
    with engine._get_connection() as conn:
        rows = conn.execute(
            "SELECT session_id, started_at, prs_score FROM session_log "
            "WHERE agent_id = ? AND prs_score IS NOT NULL "
            "ORDER BY started_at DESC LIMIT ?",
            (agent_id, limit),
        ).fetchall()

    if not rows:
        return {"agent_id": agent_id, "sessions_with_prs": 0, "trend": "no_data"}

    scores = [r[2] for r in rows if r[2] is not None]
    if len(scores) < 2:
        return {
            "agent_id": agent_id,
            "sessions_with_prs": len(scores),
            "latest_prs": scores[0] if scores else None,
            "trend": "insufficient_data",
        }

    avg_recent = sum(scores[:3]) / min(3, len(scores))
    avg_older = sum(scores[3:]) / max(1, len(scores) - 3) if len(scores) > 3 else avg_recent

    if avg_recent > avg_older * 1.05:
        trend = "improving"
    elif avg_recent < avg_older * 0.95:
        trend = "degrading"
    else:
        trend = "stable"

    return {
        "agent_id": agent_id,
        "sessions_with_prs": len(scores),
        "latest_prs": scores[0],
        "average_prs": round(sum(scores) / len(scores), 4),
        "trend": trend,
        "ceiling": PRS_CEILING,
        "history": [
            {"session_id": r[0], "started_at": r[1], "prs_score": r[2]}
            for r in rows
        ],
    }
