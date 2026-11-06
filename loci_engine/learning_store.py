#!/usr/bin/env python3
"""Persisted task-scoped lessons on the existing SQLite memory file.

Crystallized rows come only from explicit external outcome ids. Simulated
dream winners stay candidates with confidence 0. Repeating one outcome id
does not increase support. A lesson for one task_key is not a universal fact
unless a later call explicitly asks for that scope and at least two distinct
external outcome ids support it.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loci_engine.heat import MEMORY_CLASSES, evidence_accumulation, evidence_heat
from loci_engine.storage import StorageEngine

_LESSON_DDL = """
CREATE TABLE IF NOT EXISTS learning_lesson (
    id TEXT PRIMARY KEY,
    task_key TEXT NOT NULL,
    option_key TEXT NOT NULL,
    polarity TEXT NOT NULL CHECK(polarity IN ('positive', 'negative')),
    provenance_kind TEXT NOT NULL CHECK(
        provenance_kind IN ('observed_external', 'simulated_candidate', 'reflection')
    ),
    epistemic_status TEXT NOT NULL CHECK(
        epistemic_status IN ('candidate', 'crystallized', 'expired', 'superseded')
    ),
    scope TEXT NOT NULL CHECK(scope IN ('task', 'universal')),
    confidence REAL NOT NULL,
    support_count INTEGER NOT NULL,
    heat REAL NOT NULL,
    statement TEXT NOT NULL,
    evidence_json TEXT NOT NULL,
    source_event_ids TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    expires_on_day REAL,
    supersedes_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_lesson_task
    ON learning_lesson(task_key, epistemic_status, option_key);
"""

# This cycle's stored heat uses the repository open-interval law on the
# routine_observation class only. It is not a retrieval cutoff.
# It is not the ZIP table's 0.725 "sweet spot", not thermal_gradient's 0.70
# HOT tier, not LDCE's 0.50 kernel line, and not the older paper scale
# (>1.5 HOT / >0.5 WARM, or TopN in TD Commons 11666). Those scales are
# not interchangeable. Nothing here treats 0.725 as a universal gate.
_MEMORY_CLASS = MEMORY_CLASSES["routine_observation"]
HEAT_SCALE = {
    "module": "loci_engine.heat",
    "memory_class": _MEMORY_CLASS.name,
    "tau_days": _MEMORY_CLASS.tau_days,
    "alpha": _MEMORY_CLASS.alpha,
    "beta": 1.0,
    "formula": "H = alpha + (1-alpha)*(1-exp(-beta*support)) at dt=0",
    "role": "stored evidence heat, not a recall threshold",
    "universal_cutoff": None,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def heat_from_support(support_count: int, now_day: float) -> float:
    """Open-interval heat from `support_count` distinct events at `now_day`.

    Increments shrink as support grows. The value stays below 1. This is
    saturation, not exponential growth of capability.

    The class is ``HEAT_SCALE`` (routine_observation, alpha 0.05, tau 3 days).
    Passing a cutoff from another document, including 0.725, into this
    function would mix incompatible scales.
    """
    support = max(0, int(support_count))
    if support == 0:
        return 0.0
    events = [(float(now_day), 1.0, 1.0) for _ in range(support)]
    evidence = evidence_accumulation(events, now=float(now_day), tau=_MEMORY_CLASS.tau_days)
    return float(evidence_heat(evidence, alpha=_MEMORY_CLASS.alpha, beta=1.0))


def support_confidence(support_count: int) -> float:
    """Same open-interval curve as heat, reported separately from heat.

    One observation is not certainty. Extra copies of one outcome id never
    reach this function: the caller passes a count of distinct ids.
    """
    return heat_from_support(support_count, now_day=0.0)


class LearningStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.engine = StorageEngine(db_path=db_path)
        with self.engine._get_connection() as conn:
            conn.executescript(_LESSON_DDL)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def remember_candidate(
        self,
        *,
        task_key: str,
        option_key: str,
        statement: str,
        score: float,
        source: str,
    ) -> Dict[str, Any]:
        """Store a simulated or reflective note. Cannot crystallize."""
        if source not in ("simulated_candidate", "reflection"):
            raise ValueError("candidates accept only simulated_candidate or reflection")
        row = {
            "id": _uid("cand"),
            "task_key": task_key,
            "option_key": option_key,
            "polarity": "positive" if score >= 0 else "negative",
            "provenance_kind": source,
            "epistemic_status": "candidate",
            "scope": "task",
            "confidence": 0.0,
            "support_count": 0,
            "heat": 0.0,
            "statement": statement,
            "evidence_json": json.dumps({"simulated_score": score, "not_an_outcome": True}),
            "source_event_ids": json.dumps([]),
            "expires_on_day": None,
            "supersedes_id": None,
        }
        self._insert_lesson(row)
        self._mirror_memory(row, item_type="scratchpad")
        return self.get_lesson(row["id"])

    def record_observed(
        self,
        *,
        task_key: str,
        option_key: str,
        polarity: str,
        outcome_id: str,
        statement: str,
        now_day: float,
        scope_request: str = "task",
        expires_on_day: Optional[float] = None,
        quantity: Optional[float] = None,
        unit: str = "loss",
    ) -> Dict[str, Any]:
        """Crystallize or reinforce from one external outcome id.

        `scope_request='universal'` is honored only after two distinct
        external outcome ids exist. Otherwise the lesson stays task-scoped.
        """
        if polarity not in ("positive", "negative"):
            raise ValueError("polarity must be positive or negative")
        if not outcome_id:
            raise ValueError("outcome_id is required")
        if scope_request not in ("task", "universal"):
            raise ValueError("scope_request must be task or universal")

        existing = self._active_exact(task_key, option_key)
        if existing is None:
            ids = [outcome_id]
            scope = "task"
            row_id = _uid("les")
            supersedes = None
        elif existing["polarity"] != polarity:
            self._mark(existing["id"], "superseded")
            ids = [outcome_id]
            scope = "task"
            row_id = _uid("les")
            supersedes = existing["id"]
        else:
            raw_ids = existing["source_event_ids"]
            ids = list(raw_ids if isinstance(raw_ids, list) else json.loads(raw_ids))
            if outcome_id not in ids:
                ids.append(outcome_id)
            scope = existing["scope"]
            row_id = existing["id"]
            supersedes = existing["supersedes_id"]

        if scope_request == "universal" and len(ids) >= 2:
            scope = "universal"
        support = len(ids)
        heat = heat_from_support(support, now_day)
        confidence = support_confidence(support)
        row = {
            "id": row_id,
            "task_key": task_key,
            "option_key": option_key,
            "polarity": polarity,
            "provenance_kind": "observed_external",
            "epistemic_status": "crystallized",
            "scope": scope,
            "confidence": confidence,
            "support_count": support,
            "heat": heat,
            "statement": statement,
            "evidence_json": json.dumps(
                {
                    "outcome_ids": ids,
                    "scope_request": scope_request,
                    "task_specific": scope != "universal",
                    "heat_scale": HEAT_SCALE,
                    "quantity": quantity,
                    "unit": unit,
                }
            ),
            "source_event_ids": json.dumps(ids),
            "expires_on_day": expires_on_day,
            "supersedes_id": supersedes,
        }
        if existing is not None and existing["id"] == row_id and existing["polarity"] == polarity:
            self._update_lesson(row)
            self._update_memory(row)
        else:
            self._insert_lesson(row)
            self._mirror_memory(row, item_type="fact" if scope == "universal" else "observation")
        return self.get_lesson(row_id)

    def note(self, item_type: str, text: str) -> str:
        """Store a cycle trace row. Not a crystallized lesson."""
        if item_type not in ("goal_context", "decision", "summary"):
            raise ValueError("note item_type must be a trace type")
        row = {
            "id": _uid("note"),
            "task_key": "",
            "option_key": "",
            "polarity": "positive",
            "provenance_kind": "reflection",
            "epistemic_status": "candidate",
            "scope": "task",
            "confidence": 0.0,
            "support_count": 0,
            "heat": 0.0,
            "statement": text,
            "evidence_json": "{}",
            "source_event_ids": "[]",
            "expires_on_day": None,
            "supersedes_id": None,
        }
        self._mirror_memory(row, item_type=item_type)
        return row["id"]

    def active_lessons(self, task_key: str, now_day: float) -> List[Dict[str, Any]]:
        """Crystallized lessons for this task, plus universal crystallized lessons.

        Expired rows are marked expired and omitted. Candidates are omitted:
        a dream win cannot veto or endorse an option.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT * FROM learning_lesson
                WHERE epistemic_status = 'crystallized'
                  AND (task_key = ? OR scope = 'universal')
                """,
                (task_key,),
            ).fetchall()
        kept = []
        for row in rows:
            item = self._pack(row)
            expires = item["expires_on_day"]
            if expires is not None and float(now_day) >= float(expires):
                self._mark(item["id"], "expired")
                continue
            if item["provenance_kind"] != "observed_external":
                continue
            kept.append(item)
        return kept

    def get_lesson(self, lesson_id: str) -> Dict[str, Any]:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM learning_lesson WHERE id = ?", (lesson_id,)
            ).fetchone()
        if row is None:
            raise KeyError(lesson_id)
        return self._pack(row)

    def lexical_hits(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Native FTS5 order: bm25 ascending, then stored heat. Not embeddings."""
        try:
            native = self.engine.lexical_search(query, limit=limit)
        except sqlite3.OperationalError as exc:
            return {"error": str(exc), "hits": [], "native": True, "embedding": False}
        scored = []
        with self.engine._get_connection() as conn:
            try:
                rows = conn.execute(
                    """
                    SELECT m.id, m.heat, m.canonical_text, bm25(memory_item_fts) AS bm25
                    FROM memory_item m
                    JOIN memory_item_fts f ON m.id = f.item_id
                    WHERE memory_item_fts MATCH ? AND m.status = 'active'
                    ORDER BY bm25(memory_item_fts) ASC, m.heat DESC
                    LIMIT ?
                    """,
                    (query, limit),
                ).fetchall()
            except sqlite3.OperationalError as exc:
                return {"error": str(exc), "hits": [], "native": True, "embedding": False}
        for rank, row in enumerate(rows, start=1):
            scored.append(
                {
                    "id": row[0],
                    "heat": row[1],
                    "text": row[2],
                    "bm25": row[3],
                    "rank": rank,
                }
            )
        return {
            "error": None,
            "hits": scored,
            "native_ids": [row["id"] for row in native],
            "native": True,
            "embedding": False,
        }

    def _active_exact(self, task_key: str, option_key: str) -> Optional[Dict[str, Any]]:
        with self._conn() as conn:
            row = conn.execute(
                """
                SELECT * FROM learning_lesson
                WHERE task_key = ? AND option_key = ? AND epistemic_status = 'crystallized'
                """,
                (task_key, option_key),
            ).fetchone()
        return self._pack(row) if row else None

    def _insert_lesson(self, row: Dict[str, Any]) -> None:
        now = _now_iso()
        with self._conn() as conn:
            conn.execute(
                """
                INSERT INTO learning_lesson (
                    id, task_key, option_key, polarity, provenance_kind, epistemic_status,
                    scope, confidence, support_count, heat, statement, evidence_json,
                    source_event_ids, created_at, updated_at, expires_on_day, supersedes_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["id"], row["task_key"], row["option_key"], row["polarity"],
                    row["provenance_kind"], row["epistemic_status"], row["scope"],
                    row["confidence"], row["support_count"], row["heat"], row["statement"],
                    row["evidence_json"], row["source_event_ids"], now, now,
                    row["expires_on_day"], row["supersedes_id"],
                ),
            )
            conn.commit()

    def _update_lesson(self, row: Dict[str, Any]) -> None:
        with self._conn() as conn:
            conn.execute(
                """
                UPDATE learning_lesson
                SET scope = ?, confidence = ?, support_count = ?, heat = ?,
                    statement = ?, evidence_json = ?, source_event_ids = ?,
                    updated_at = ?, expires_on_day = ?
                WHERE id = ?
                """,
                (
                    row["scope"], row["confidence"], row["support_count"], row["heat"],
                    row["statement"], row["evidence_json"], row["source_event_ids"],
                    _now_iso(), row["expires_on_day"], row["id"],
                ),
            )
            conn.commit()

    def _mark(self, lesson_id: str, status: str) -> None:
        with self._conn() as conn:
            conn.execute(
                "UPDATE learning_lesson SET epistemic_status = ?, updated_at = ? WHERE id = ?",
                (status, _now_iso(), lesson_id),
            )
            conn.commit()
        now = _now_iso()
        with self.engine._get_connection() as conn:
            conn.execute(
                """
                UPDATE memory_item
                SET status = 'superseded', valid_until = ?, updated_at = ?
                WHERE id = ? AND status = 'active'
                """,
                (now, now, lesson_id),
            )

    def _mirror_memory(self, row: Dict[str, Any], item_type: str) -> None:
        now = _now_iso()
        text = row["statement"]
        meta = {
            "task_key": row["task_key"],
            "option_key": row["option_key"],
            "polarity": row["polarity"],
            "provenance_kind": row["provenance_kind"],
            "epistemic_status": row["epistemic_status"],
            "scope": row["scope"],
            "support_count": row["support_count"],
            "confidence": row["confidence"],
        }
        heat = min(1.0, max(0.0, float(row["heat"])))
        with self.engine._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO memory_item (
                    id, namespace, item_type, canonical_text, lexical_text,
                    source_event_id, source_actor, source_trust, confidence,
                    sensitivity, era, alpha, heat, last_observed_at, valid_from,
                    status, content_hash, created_at, updated_at, metadata_json
                ) VALUES (
                    ?, 'learning_loop', ?, ?, ?, ?, 'learning_cycle', ?, ?,
                    'internal', 'near', ?, ?, ?, ?, 'active', ?, ?, ?, ?
                )
                """,
                (
                    row["id"], item_type, text, text.lower(),
                    row["id"],
                    0.0 if row["provenance_kind"] != "observed_external" else 0.5,
                    min(1.0, max(0.0, float(row["confidence"]))),
                    _MEMORY_CLASS.alpha, heat, now, now,
                    _sha(text), now, now, json.dumps(meta),
                ),
            )

    def _update_memory(self, row: Dict[str, Any]) -> None:
        now = _now_iso()
        text = row["statement"]
        item_type = "fact" if row["scope"] == "universal" else "observation"
        meta = {
            "task_key": row["task_key"],
            "option_key": row["option_key"],
            "polarity": row["polarity"],
            "provenance_kind": row["provenance_kind"],
            "epistemic_status": row["epistemic_status"],
            "scope": row["scope"],
            "support_count": row["support_count"],
            "confidence": row["confidence"],
        }
        with self.engine._get_connection() as conn:
            conn.execute(
                """
                UPDATE memory_item
                SET canonical_text = ?, lexical_text = ?, heat = ?, confidence = ?,
                    item_type = ?, updated_at = ?, metadata_json = ?, content_hash = ?
                WHERE id = ?
                """,
                (
                    text, text.lower(), min(1.0, max(0.0, float(row["heat"]))),
                    min(1.0, max(0.0, float(row["confidence"]))),
                    item_type, now, json.dumps(meta), _sha(text), row["id"],
                ),
            )

    @staticmethod
    def _pack(row: sqlite3.Row) -> Dict[str, Any]:
        item = dict(row)
        item["source_event_ids"] = json.loads(item["source_event_ids"])
        item["evidence"] = json.loads(item["evidence_json"])
        return item


def _sha(text: str) -> str:
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
