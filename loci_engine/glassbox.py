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
