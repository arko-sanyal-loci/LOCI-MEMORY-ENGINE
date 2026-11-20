"""
loci_engine/db.py
=================
Shared SQLite connection helper.

Every LOCI store that opens its own SQLite file (``vectors.VectorStore`` for
RAG chunks; ``storage.StorageEngine`` manages ``context2.db`` itself) should
open it in WAL mode, so a reader (for example a query from the compact model
lane) never blocks on a concurrent writer (a fact update from the expand
lane).

Ported 2026-11-19 from the September engine. That version also executed a
``schema.sql`` with ``isymprev``/``qsymprev`` tables; those tables are NOT
ported, because the canonical engine stores entities and facts in
``storage.py``'s ``memory_item`` table (see the ``store.py`` docstring) and a
second parallel schema would split the memory in two.
"""
from __future__ import annotations

import os
import sqlite3


def open_db(path: str, *, timeout: float = 30.0) -> sqlite3.Connection:
    """Open (creating parent directories if needed) a WAL-mode SQLite file."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent:
        os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, timeout=timeout)
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
    except Exception:
        conn.close()
        raise
    return conn
