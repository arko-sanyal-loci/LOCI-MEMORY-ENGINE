#!/usr/bin/env python3
"""
Loci Memory Engine - Cold Storage Substrate (context2.db)
Implements Compendium Section 2: SQLite WAL, Append-Only Fact Lineage, FTS5 & GCSD Locks.
"""

import sqlite3
import os
import json
import hashlib
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

DB_PATH = os.getenv("LOCI_DB_PATH", os.path.expanduser("~/loci-memory-engine/context2.db"))

# Paper 08: asymmetric trust gate thresholds
_TRUST_FLOOR = 0.8      # new_trust must be >= old_trust * 0.8 to supersede
_TRUST_DOMINANT = 1.2   # new_trust >= old_trust * 1.2 → unconditional supersession

DDL_SCHEMA = """
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA temp_store = MEMORY;
PRAGMA mmap_size = 268435456;
PRAGMA cache_size = -64000;

CREATE TABLE IF NOT EXISTS memory_item (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    item_type TEXT NOT NULL CHECK(item_type IN ('fact', 'invariant', 'goal_context', 'decision', 'observation', 'tool_result', 'summary', 'policy', 'scratchpad')),
    canonical_text TEXT NOT NULL,
    structured_value TEXT,
    embedding_ref TEXT,
    lexical_text TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    source_uri TEXT,
    source_actor TEXT NOT NULL,
    source_trust REAL NOT NULL CHECK(source_trust >= 0.0 AND source_trust <= 1.0),
    confidence REAL NOT NULL CHECK(confidence >= 0.0 AND confidence <= 1.0),
    sensitivity TEXT NOT NULL CHECK(sensitivity IN ('public', 'internal', 'confidential', 'local_only')),
    era TEXT NOT NULL CHECK(era IN ('far', 'mid', 'near')),
    alpha REAL NOT NULL CHECK(alpha >= 0.0 AND alpha <= 1.0),
    heat REAL NOT NULL CHECK(heat >= 0.0 AND heat <= 1.0),
    last_observed_at TEXT NOT NULL,
    valid_from TEXT NOT NULL,
    valid_until TEXT,
    status TEXT NOT NULL CHECK(status IN ('candidate', 'active', 'superseded', 'rejected', 'quarantined', 'archived')),
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    supersedes_id TEXT REFERENCES memory_item(id),
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_mem_item_ns_status_era ON memory_item(namespace, status, era);
CREATE INDEX IF NOT EXISTS idx_mem_item_validity ON memory_item(valid_from, valid_until);
CREATE INDEX IF NOT EXISTS idx_mem_item_content_hash ON memory_item(content_hash);
CREATE INDEX IF NOT EXISTS idx_mem_item_heat ON memory_item(heat DESC);

CREATE TABLE IF NOT EXISTS goal_state (
    goal_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    objective TEXT NOT NULL,
    constraints_json TEXT NOT NULL DEFAULT '[]',
    foreground_status TEXT NOT NULL CHECK(foreground_status IN ('proposed', 'active', 'paused', 'completed', 'aborted', 'retired')),
    background_invariant INTEGER NOT NULL DEFAULT 0 CHECK(background_invariant IN (0, 1)),
    priority INTEGER NOT NULL DEFAULT 1,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    aborted_at TEXT,
    last_progress_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS goal_lock (
    id TEXT PRIMARY KEY,
    goal_id TEXT NOT NULL REFERENCES goal_state(goal_id) ON DELETE CASCADE,
    memory_item_id TEXT NOT NULL REFERENCES memory_item(id) ON DELETE CASCADE,
    lock_strength TEXT NOT NULL CHECK(lock_strength IN ('anchor', 'dependency')),
    lock_reason TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    release_event_id TEXT
);

CREATE VIRTUAL TABLE IF NOT EXISTS memory_item_fts USING fts5(
    item_id UNINDEXED,
    canonical_text,
    lexical_text,
    tokenize = 'porter unicode61'
);

CREATE TRIGGER IF NOT EXISTS trig_memory_item_ai AFTER INSERT ON memory_item
BEGIN
    INSERT INTO memory_item_fts (item_id, canonical_text, lexical_text)
    VALUES (new.id, new.canonical_text, new.lexical_text);
END;

CREATE TRIGGER IF NOT EXISTS trig_memory_item_ad AFTER DELETE ON memory_item
BEGIN
    DELETE FROM memory_item_fts WHERE item_id = old.id;
END;
"""

class StorageEngine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        # The default lives under ~/loci-memory-engine/, which may not exist on a
        # fresh machine; sqlite then fails with "unable to open database file".
        parent = os.path.dirname(os.path.abspath(db_path))
        if db_path != ":memory:" and parent:
            os.makedirs(parent, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            conn.executescript(DDL_SCHEMA)

    @staticmethod
    def _utc_now() -> str:
        return datetime.now(timezone.utc).isoformat()

    def insert_fact(
        self,
        item_id: str,
        namespace: str,
        canonical_text: str,
        heat: float = 0.85,
        source_trust: float = 0.95,
        era: str = "mid",
        alpha: float = 0.01,
        supersedes_id: Optional[str] = None,
        source_actor: str = "kernel",
    ) -> str:
        now = self._utc_now()
        content_hash = hashlib.sha256(canonical_text.encode("utf-8")).hexdigest()

        with self._get_connection() as conn:
            cur = conn.cursor()
            # If superseding, terminate previous record's valid_until interval
            if supersedes_id:
                cur.execute(
                    "UPDATE memory_item SET valid_until = ?, status = 'superseded' WHERE id = ?",
                    (now, supersedes_id)
                )

            cur.execute("""
                INSERT INTO memory_item (
                    id, namespace, item_type, canonical_text, lexical_text,
                    source_event_id, source_actor, source_trust, confidence,
                    sensitivity, era, alpha, heat, last_observed_at,
                    valid_from, status, content_hash, created_at, updated_at,
                    supersedes_id
                ) VALUES (?, ?, 'fact', ?, ?, 'evt_boot', ?, ?, 1.0, 'local_only', ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
            """, (
                item_id, namespace, canonical_text, canonical_text.lower(),
                source_actor, source_trust, era, alpha, heat, now, now, content_hash, now, now, supersedes_id
            ))
            conn.commit()
        return item_id

    def lexical_search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT m.* FROM memory_item m
                JOIN memory_item_fts f ON m.id = f.item_id
                WHERE memory_item_fts MATCH ? AND m.status = 'active'
                ORDER BY bm25(memory_item_fts) ASC, m.heat DESC LIMIT ?
            """, (query, limit))
            rows = cur.fetchall()
            return [dict(r) for r in rows]

    def fetch_active_items(
        self,
        namespace: Optional[str] = None,
        source_actor: Optional[str] = None,
        limit: int = 500,
    ) -> List[Dict[str, Any]]:
        """Return active memory_item rows as dicts, pre-filtered for CARD."""
        clauses = ["status = 'active'"]
        params: list = []

        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if source_actor:
            clauses.append("source_actor = ?")
            params.append(source_actor)

        where = " AND ".join(clauses)
        params.append(limit)

        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                f"SELECT * FROM memory_item WHERE {where} "
                f"ORDER BY heat DESC LIMIT ?",
                params,
            )
            rows = cur.fetchall()

        result = []
        for row in rows:
            item = dict(row)
            item.setdefault("timestamp", item.get("created_at", ""))
            result.append(item)
        return result

    def decay_stored_heat(
        self,
        tau_days: Optional[float] = None,
        alpha: float = 0.05,
        reference_time: Optional[str] = None,
    ) -> int:
        """Recompute and persist heat using tier-aware tau values (Spark, Nov 2026).

        When tau_days is None (default), each item's tau is chosen by its
        current heat tier per the canonical hardware schema in heat.py:
          HOT  (H >= 0.80): tau = 1.25 days
          MILD (H >= 0.35): tau = 1.75 days
          COLD (H <  0.35): tau = 2.25 days
        Pass an explicit tau_days to override tier-aware selection.
        """
        import math as _math
        from datetime import datetime as _dt, timezone as _tz
        from loci_engine.heat import TIER_TAU, TIER_HOT_BOUNDARY, TIER_MILD_BOUNDARY

        now_str = reference_time or self._utc_now()
        try:
            now_dt = _dt.fromisoformat(now_str)
        except ValueError:
            now_dt = _dt.now(_tz.utc)

        updated = 0
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, last_observed_at, alpha, heat FROM memory_item "
                "WHERE status = 'active'"
            )
            rows = cur.fetchall()

            for row in rows:
                try:
                    last_obs = _dt.fromisoformat(row["last_observed_at"])
                except (ValueError, TypeError):
                    continue

                elapsed = max(0.0, (now_dt - last_obs).total_seconds() / 86400.0)
                item_alpha = row["alpha"] if row["alpha"] > 0 else alpha

                # Tier-aware tau unless caller overrides
                if tau_days is not None:
                    effective_tau = tau_days
                elif row["heat"] >= TIER_HOT_BOUNDARY:
                    effective_tau = TIER_TAU["hot"]
                elif row["heat"] >= TIER_MILD_BOUNDARY:
                    effective_tau = TIER_TAU["mild"]
                else:
                    effective_tau = TIER_TAU["cold"]

                evidence = 1.0 / (1.0 + elapsed / effective_tau)
                raw = item_alpha + (1.0 - item_alpha) * (1.0 - _math.exp(-evidence))
                new_heat = max(item_alpha + 1e-9, min(1.0 - 1e-9, raw))

                if abs(new_heat - row["heat"]) > 1e-6:
                    cur.execute(
                        "UPDATE memory_item SET heat = ?, updated_at = ? WHERE id = ?",
                        (new_heat, now_str, row["id"]),
                    )
                    updated += 1

            conn.commit()
        return updated

    # ------------------------------------------------------------------
    # Paper 08 — Persistent Memory Engine: structured fact versioning
    # ------------------------------------------------------------------

    @staticmethod
    def _fact_key(entity_id: str, key: str) -> str:
        return f"{entity_id}\x1f{key}"

    def _get_active_fact(self, namespace: str, fact_key: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM memory_item WHERE namespace = ? AND item_type = 'fact' "
                "AND lexical_text = ? AND status = 'active' ORDER BY valid_from DESC LIMIT 1",
                (namespace, fact_key),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def upsert_fact(
        self,
        entity_id: str,
        key: str,
        value: Any,
        source_trust: float = 0.95,
        namespace: str = "facts",
        source_actor: str = "kernel",
    ) -> Dict[str, Any]:
        fact_key = self._fact_key(entity_id, key)
        structured = json.dumps({"entity_id": entity_id, "key": key, "value": value})
        canonical = f"{entity_id}.{key} = {value}"
        new_id = str(uuid.uuid4())

        existing = self._get_active_fact(namespace, fact_key)

        if existing:
            old_trust = existing["source_trust"]
            trust_ratio = source_trust / old_trust if old_trust > 0 else float("inf")

            if trust_ratio < _TRUST_FLOOR:
                return {
                    "accepted": False,
                    "action": "rejected",
                    "reason": "trust_below_floor",
                    "trust_ratio": round(trust_ratio, 4),
                    "existing_id": existing["id"],
                }

            dominant = trust_ratio >= _TRUST_DOMINANT
            self.insert_fact(
                item_id=new_id,
                namespace=namespace,
                canonical_text=canonical,
                source_trust=source_trust,
                source_actor=source_actor,
                supersedes_id=existing["id"],
            )
            with self._get_connection() as conn:
                conn.execute(
                    "UPDATE memory_item SET structured_value = ?, lexical_text = ? WHERE id = ?",
                    (structured, fact_key, new_id),
                )
            return {
                "accepted": True,
                "action": "superseded",
                "id": new_id,
                "superseded_id": existing["id"],
                "trust_ratio": round(trust_ratio, 4),
                "dominant": dominant,
            }

        self.insert_fact(
            item_id=new_id,
            namespace=namespace,
            canonical_text=canonical,
            source_trust=source_trust,
            source_actor=source_actor,
        )
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE memory_item SET structured_value = ?, lexical_text = ? WHERE id = ?",
                (structured, fact_key, new_id),
            )
        return {"accepted": True, "action": "inserted", "id": new_id}

    def get_current_fact(
        self, entity_id: str, key: str, namespace: str = "facts"
    ) -> Optional[Dict[str, Any]]:
        return self._get_active_fact(namespace, self._fact_key(entity_id, key))

    def get_fact_at(
        self, entity_id: str, key: str, as_of: str, namespace: str = "facts"
    ) -> Optional[Dict[str, Any]]:
        fact_key = self._fact_key(entity_id, key)
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM memory_item WHERE namespace = ? AND item_type = 'fact' "
                "AND lexical_text = ? AND valid_from <= ? "
                "AND (valid_until IS NULL OR valid_until > ?) "
                "ORDER BY valid_from DESC LIMIT 1",
                (namespace, fact_key, as_of, as_of),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def get_fact_history(
        self, entity_id: str, key: str, namespace: str = "facts"
    ) -> List[Dict[str, Any]]:
        fact_key = self._fact_key(entity_id, key)
        with self._get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM memory_item WHERE namespace = ? AND item_type = 'fact' "
                "AND lexical_text = ? ORDER BY valid_from DESC",
                (namespace, fact_key),
            )
            return [dict(r) for r in cur.fetchall()]

    def ingest_session_turn(
        self,
        turn_id: str,
        role: str,
        content: str,
        namespace: str = "session",
        heat: float = 0.75,
        era: str = "near",
        source_actor: str = "user",
    ) -> str:
        """Write a single conversation turn to memory_item."""
        return self.insert_fact(
            item_id=turn_id,
            namespace=namespace,
            canonical_text=f"[{role.upper()}] {content}",
            heat=heat,
            source_actor=source_actor,
            source_trust=1.0,
            era=era,
        )
