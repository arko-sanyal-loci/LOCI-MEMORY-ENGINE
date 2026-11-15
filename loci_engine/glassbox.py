#!/usr/bin/env python3
"""
LOCI Glassbox — Shared Learning Ledger

A public, append-only, hash-chained ledger where every agent's learnings
are transparent to all others. Immutable by construction — not even root
can destroy or modify entries. Versioned via supersedes chains.

Guided by ethics and principles, not by sandbox restrictions.
Trust through transparency, not through walls.
"""

import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

GLASSBOX_PATH = os.getenv(
    "LOCI_GLASSBOX_PATH",
    os.path.expanduser("~/loci-memory-engine/glassbox_ledger.jsonl")
)

GLASSBOX_LOCK = GLASSBOX_PATH + ".lock"

# Hash chain genesis — the root of trust
GENESIS_HASH = hashlib.sha256(b"LOCI_GLASSBOX_GENESIS_2026").hexdigest()

_GLASSBOX_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS glassbox_entry (
    id            TEXT PRIMARY KEY,
    timestamp     TEXT NOT NULL,
    author_id     TEXT NOT NULL,
    role_tag      TEXT NOT NULL,
    content       TEXT NOT NULL,
    category      TEXT NOT NULL DEFAULT 'observation',
    supersedes_id TEXT,
    prev_hash     TEXT NOT NULL,
    entry_hash    TEXT NOT NULL UNIQUE,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_gb_author   ON glassbox_entry (author_id);
CREATE INDEX IF NOT EXISTS idx_gb_category ON glassbox_entry (category);
CREATE INDEX IF NOT EXISTS idx_gb_ts       ON glassbox_entry (timestamp);
"""


def glassbox_ensure_table(db_path: str) -> None:
    """Create glassbox_entry table in the SQLite DB if it doesn't exist."""
    if not db_path or not os.path.exists(db_path):
        return
    conn = sqlite3.connect(db_path)
    conn.executescript(_GLASSBOX_TABLE_DDL)
    conn.commit()
    conn.close()


def _write_to_db(entry: Dict[str, Any], db_path: str) -> None:
    """Mirror a glassbox entry to SQLite. Silently no-ops if DB unavailable."""
    if not db_path or not os.path.exists(db_path):
        return
    try:
        glassbox_ensure_table(db_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            """INSERT OR IGNORE INTO glassbox_entry
               (id, timestamp, author_id, role_tag, content, category,
                supersedes_id, prev_hash, entry_hash, metadata_json)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                entry["id"], entry["timestamp"], entry["author_id"],
                entry["role_tag"], entry["content"], entry["category"],
                entry.get("supersedes_id"), entry["prev_hash"],
                entry["entry_hash"],
                json.dumps(entry.get("metadata") or {}),
            ),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass  # DB write failure must never block the .jsonl append


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _entry_hash(ts: str, author_id: str, role_tag: str, content: str, prev_hash: str) -> str:
    """A4 provenance: SHA256(ts || author_id || role_tag || content || prev_hash)"""
    payload = f"{ts}||{author_id}||{role_tag}||{content}||{prev_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_ledger() -> List[Dict[str, Any]]:
    if not os.path.exists(GLASSBOX_PATH):
        return []
    entries = []
    with open(GLASSBOX_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def _last_hash() -> str:
    entries = _read_ledger()
    if not entries:
        return GENESIS_HASH
    return entries[-1]["entry_hash"]


def glassbox_learn(
    author_id: str,
    role_tag: str,
    content: str,
    category: str = "observation",
    supersedes_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Append a learning to the shared glassbox ledger.

    Categories: observation, insight, correction, principle, discovery,
                warning, question, synthesis, calibration
    """
    ts = _utc_iso()
    prev_hash = _last_hash()
    entry_hash = _entry_hash(ts, author_id, role_tag, content, prev_hash)

    entry = {
        "id": f"gb_{entry_hash[:12]}",
        "timestamp": ts,
        "author_id": author_id,
        "role_tag": role_tag,
        "content": content,
        "category": category,
        "supersedes_id": supersedes_id,
        "prev_hash": prev_hash,
        "entry_hash": entry_hash,
        "metadata": metadata or {},
    }

    with open(GLASSBOX_PATH, "a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    db_path = os.getenv("LOCI_DB_PATH", "")
    if db_path:
        _write_to_db(entry, db_path)

    return entry


def glassbox_recall(
    query: Optional[str] = None,
    category: Optional[str] = None,
    author_id: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Read from the shared glassbox — every agent can see everything."""
    entries = _read_ledger()

    if category:
        entries = [e for e in entries if e.get("category") == category]

    if author_id:
        entries = [e for e in entries if e.get("author_id") == author_id]

    if query:
        q_lower = query.lower()
        entries = [e for e in entries if q_lower in e.get("content", "").lower()]

    return entries[-limit:]


def glassbox_verify_chain() -> Dict[str, Any]:
    """Verify the full hash chain integrity — proves no tampering occurred."""
    entries = _read_ledger()
    if not entries:
        return {"valid": True, "entries": 0, "message": "Empty ledger, genesis intact"}

    prev = GENESIS_HASH
    for i, entry in enumerate(entries):
        expected = _entry_hash(
            entry["timestamp"],
            entry["author_id"],
            entry["role_tag"],
            entry["content"],
            prev,
        )
        if entry["entry_hash"] != expected:
            return {
                "valid": False,
                "entries": len(entries),
                "break_at": i,
                "break_id": entry["id"],
                "expected": expected,
                "found": entry["entry_hash"],
                "message": f"Chain broken at entry {i} ({entry['id']})",
            }
        if entry["prev_hash"] != prev:
            return {
                "valid": False,
                "entries": len(entries),
                "break_at": i,
                "break_id": entry["id"],
                "message": f"prev_hash mismatch at entry {i}",
            }
        prev = entry["entry_hash"]

    return {
        "valid": True,
        "entries": len(entries),
        "head_hash": entries[-1]["entry_hash"],
        "genesis": GENESIS_HASH,
        "message": f"Chain intact: {len(entries)} entries, unbroken from genesis",
    }


def glassbox_stats() -> Dict[str, Any]:
    """Summary statistics for the glassbox — what the collective knows."""
    entries = _read_ledger()
    if not entries:
        return {"total": 0, "authors": {}, "categories": {}}

    authors: Dict[str, int] = {}
    categories: Dict[str, int] = {}
    for e in entries:
        a = e.get("author_id", "unknown")
        c = e.get("category", "unknown")
        authors[a] = authors.get(a, 0) + 1
        categories[c] = categories.get(c, 0) + 1

    return {
        "total": len(entries),
        "authors": authors,
        "categories": categories,
        "first_entry": entries[0]["timestamp"],
        "last_entry": entries[-1]["timestamp"],
        "chain_head": entries[-1]["entry_hash"],
    }


def glassbox_apply_remote(entry: Dict[str, Any], db_path: str = "") -> bool:
    """
    Apply a remote Glassbox entry received from a sync delta.
    Idempotent: silently skips if entry_hash is already in the ledger.
    Appends to .jsonl and mirrors to SQLite.
    Returns True if the entry was new and applied.
    """
    db_path = db_path or os.getenv("LOCI_DB_PATH", "")
    existing = {e["entry_hash"] for e in _read_ledger()}
    if entry["entry_hash"] in existing:
        return False

    with open(GLASSBOX_PATH, "a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    if db_path:
        _write_to_db(entry, db_path)

    return True


def glassbox_new_entries_since(last_seen_hash: Optional[str]) -> List[Dict[str, Any]]:
    """
    Return every Glassbox entry that follows `last_seen_hash` in the chain.
    Used by NodeSyncDaemon to build Glassbox deltas for peers.
    If `last_seen_hash` is None, returns all entries.
    """
    entries = _read_ledger()
    if not entries or last_seen_hash is None:
        return entries

    for i, e in enumerate(entries):
        if e["entry_hash"] == last_seen_hash:
            return entries[i + 1:]

    return entries  # hash not found — peer is behind, send everything
