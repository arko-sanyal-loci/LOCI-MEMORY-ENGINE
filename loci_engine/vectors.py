"""
loci_engine/vectors.py
======================
Hybrid chunk store for the RAG pipeline (Organisation pillar).

One SQLite file holds three views of every document chunk:

  chunk_meta  — text, JSON metadata, and a heat/last_used pair
  vec_chunks  — dense embedding (sqlite-vec ``vec0`` virtual table)
  fts_chunks  — sparse BM25 index (SQLite FTS5)

``query()`` fuses the dense and sparse rankings with Reciprocal Rank Fusion
(RRF, k=60), then, for each chunk it returns, ages its heat forward with
``heat.decay()`` (tier-aware τ) and reinforces it with ``heat.reinforce()``.
So chunks that keep being retrieved climb toward HOT and chunks that are
never retrieved cool toward the α floor, which is what makes heat usable by
``rag.card.apply_ranking_strategy`` as a ranking signal.

Ported 2026-11-19 from the September engine (loci-memory-engine-1,
``loci-engine/loci_engine/vectors.py``). That version used the old 0–1
exponential heat law (``decay(h, days)`` and ``apply_increment``); this one
uses the canonical hyperbolic law in ``loci_engine.heat``.

Requires the ``sqlite-vec`` package (``pip install sqlite-vec``).
"""
import json
import os
import re
import struct
import time

from loci_engine.db import open_db
from loci_engine.heat import ALPHA_FLOOR, decay, reinforce, tier_tau

EMBEDDING_DIM = 768
RRF_K = 60


def _to_blob(vector: list[float]) -> bytes:
    return struct.pack(f"{len(vector)}f", *vector)


def _to_fts5_query(text: str) -> str | None:
    """Turn arbitrary user text into a safe FTS5 MATCH query.

    Natural-language input (e.g. "What color is the sky?") contains characters
    that are significant to FTS5's own query syntax (?, -, ^, *, (, ), :, etc.)
    and raises `sqlite3.OperationalError: fts5: syntax error` if passed through
    unescaped. Extracting word tokens and quoting each one neutralizes any
    operator meaning; joining with OR keeps the search permissive (a BM25
    relevance signal, not a strict all-terms-must-match filter) since most
    natural questions contain stopwords that won't appear in every match.
    """
    tokens = re.findall(r"\w+", text)
    if not tokens:
        return None
    return " OR ".join(f'"{token}"' for token in tokens)


DEFAULT_CHUNK_HEAT = 0.333  # new chunks start MILD, below θ_HOT


class VectorStore:
    """Dense + sparse chunk store with heat tracking. See module docstring."""

    def __init__(self, path: str, embedding_dim: int = EMBEDDING_DIM):
        if os.path.isdir(path):
            raise RuntimeError(
                f"{path!r} is a directory (looks like a leftover Chroma store) — "
                "VectorStore needs a file path; point RAG_DB_PATH at a new "
                "file, e.g. ./loci.db"
            )
        self._conn = open_db(path)
        self._conn.enable_load_extension(True)
        import sqlite_vec

        sqlite_vec.load(self._conn)
        self._conn.enable_load_extension(False)
        self._conn.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS chunk_meta (
                chunk_id TEXT PRIMARY KEY,
                rowid_map INTEGER UNIQUE,
                text TEXT NOT NULL,
                metadata TEXT NOT NULL,
                heat REAL DEFAULT {DEFAULT_CHUNK_HEAT},
                last_used REAL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS vec_chunks USING vec0(
                embedding float[{embedding_dim}]
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS fts_chunks USING fts5(
                chunk_id UNINDEXED, text
            );
            """
        )
        # CREATE TABLE IF NOT EXISTS is a no-op against a chunk_meta table that
        # already existed before heat/last_used were added (Plan 3 Task 3) - it
        # does not retroactively add columns. Migrate any pre-existing database
        # here so `heat` reads never hit "no such column" on a database created
        # before this change.
        existing_columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(chunk_meta)")
        }
        if "heat" not in existing_columns:
            self._conn.execute(f"ALTER TABLE chunk_meta ADD COLUMN heat REAL DEFAULT {DEFAULT_CHUNK_HEAT}")
        if "last_used" not in existing_columns:
            self._conn.execute("ALTER TABLE chunk_meta ADD COLUMN last_used REAL")
        self._conn.commit()

    def add(
        self,
        ids: list[str],
        embeddings: list[list[float]],
        texts: list[str],
        metadatas: list[dict],
    ) -> None:
        """Insert or update chunks. Re-adding an id replaces its text,
        metadata and embedding but keeps its accumulated heat."""
        for chunk_id, embedding, text, metadata in zip(ids, embeddings, texts, metadatas):
            existing = self._conn.execute(
                "SELECT rowid_map FROM chunk_meta WHERE chunk_id = ?", (chunk_id,)
            ).fetchone()
            if existing is not None:
                row_id = existing[0]
                self._conn.execute(
                    "UPDATE chunk_meta SET text = ?, metadata = ? WHERE chunk_id = ?",
                    (text, json.dumps(metadata), chunk_id),
                )
                self._conn.execute(
                    "UPDATE vec_chunks SET embedding = ? WHERE rowid = ?",
                    (_to_blob(embedding), row_id),
                )
                self._conn.execute(
                    "UPDATE fts_chunks SET text = ? WHERE chunk_id = ?", (text, chunk_id)
                )
            else:
                cursor = self._conn.execute(
                    "INSERT INTO chunk_meta (chunk_id, text, metadata, last_used) "
                    "VALUES (?, ?, ?, ?)",
                    (chunk_id, text, json.dumps(metadata), time.time()),
                )
                row_id = cursor.lastrowid
                self._conn.execute(
                    "UPDATE chunk_meta SET rowid_map = ? WHERE chunk_id = ?",
                    (row_id, chunk_id),
                )
                self._conn.execute(
                    "INSERT INTO vec_chunks (rowid, embedding) VALUES (?, ?)",
                    (row_id, _to_blob(embedding)),
                )
                self._conn.execute(
                    "INSERT INTO fts_chunks (chunk_id, text) VALUES (?, ?)", (chunk_id, text)
                )
        self._conn.commit()

    def query(
        self,
        embedding: list[float],
        top_k: int = 5,
        query_text: str | None = None,
    ) -> list[dict]:
        """Return the ``top_k`` chunks by RRF over dense + sparse ranks.

        Each result is ``{id, text, metadata, distance, heat}``. Retrieval is
        itself evidence of relevance, so every returned chunk is decayed to
        now and then reinforced (hop 0) before being returned.
        """
        fetch_k = max(top_k * 4, top_k)
        dense_rows = self._conn.execute(
            """
            SELECT chunk_meta.chunk_id, vec_chunks.distance
            FROM vec_chunks
            JOIN chunk_meta ON chunk_meta.rowid_map = vec_chunks.rowid
            WHERE embedding MATCH ? AND k = ?
            ORDER BY distance
            """,
            (_to_blob(embedding), fetch_k),
        ).fetchall()
        dense_rank = {chunk_id: rank for rank, (chunk_id, _) in enumerate(dense_rows)}
        dense_distance = {chunk_id: distance for chunk_id, distance in dense_rows}

        sparse_rank: dict[str, int] = {}
        fts5_query = _to_fts5_query(query_text) if query_text else None
        if fts5_query:
            sparse_rows = self._conn.execute(
                """
                SELECT chunk_id FROM fts_chunks
                WHERE fts_chunks MATCH ? ORDER BY bm25(fts_chunks) LIMIT ?
                """,
                (fts5_query, fetch_k),
            ).fetchall()
            sparse_rank = {chunk_id: rank for rank, (chunk_id,) in enumerate(sparse_rows)}

        all_ids = set(dense_rank) | set(sparse_rank)
        scored = [
            (
                chunk_id,
                (1.0 / (RRF_K + dense_rank[chunk_id] + 1) if chunk_id in dense_rank else 0.0)
                + (1.0 / (RRF_K + sparse_rank[chunk_id] + 1) if chunk_id in sparse_rank else 0.0),
            )
            for chunk_id in all_ids
        ]
        scored.sort(key=lambda pair: (-pair[1], pair[0]))

        now = time.time()
        results = []
        for chunk_id, _ in scored[:top_k]:
            row = self._conn.execute(
                "SELECT text, metadata, heat, last_used FROM chunk_meta WHERE chunk_id = ?",
                (chunk_id,),
            ).fetchone()
            text, metadata_json, heat, last_used = row
            days_elapsed = max(0.0, (now - (last_used or now)) / 86400.0)
            current = heat if heat is not None else DEFAULT_CHUNK_HEAT
            decayed = max(ALPHA_FLOOR, decay(current, days_elapsed, tier_tau(current)))
            new_heat = reinforce(decayed, hop=0)
            self._conn.execute(
                "UPDATE chunk_meta SET heat = ?, last_used = ? WHERE chunk_id = ?",
                (new_heat, now, chunk_id),
            )
            results.append(
                {
                    "id": chunk_id,
                    "text": text,
                    "metadata": json.loads(metadata_json),
                    "distance": dense_distance.get(chunk_id),
                    "heat": new_heat,
                }
            )
        self._conn.commit()
        return results

    def count(self) -> int:
        """Number of stored chunks."""
        return self._conn.execute("SELECT COUNT(*) FROM chunk_meta").fetchone()[0]

    def close(self) -> None:
        self._conn.close()
