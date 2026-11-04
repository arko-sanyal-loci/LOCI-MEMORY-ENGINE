#!/usr/bin/env python3
"""
Loci Memory Engine - Cold Storage Substrate (context2.db)
Implements Compendium Section 2: SQLite WAL, Append-Only Fact Lineage, FTS5 & GCSD Locks.
"""

import sqlite3
import os
import json
import hashlib
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

DB_PATH = os.getenv("LOCI_DB_PATH", os.path.expanduser("~/loci-memory-engine/context2.db"))

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
        supersedes_id: Optional[str] = None
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
                ) VALUES (?, ?, 'fact', ?, ?, 'evt_boot', 'kernel', ?, 1.0, 'local_only', ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?)
            """, (
                item_id, namespace, canonical_text, canonical_text.lower(),
                source_trust, era, alpha, heat, now, now, content_hash, now, now, supersedes_id
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
