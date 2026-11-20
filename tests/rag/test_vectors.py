import sqlite3
import json

import pytest

from loci_engine.vectors import VectorStore


def test_close_closes_the_underlying_connection(tmp_path):
    store = VectorStore(str(tmp_path / "loci.db"))

    store.close()

    with pytest.raises(Exception):
        store._conn.execute("SELECT 1")


def test_init_enables_wal_mode(tmp_path):
    store = VectorStore(str(tmp_path / "loci.db"))

    mode = store._conn.execute("PRAGMA journal_mode").fetchone()[0]

    assert mode.lower() == "wal"


def test_add_then_query_returns_closest_dense_match_first(tmp_path):
    store = VectorStore(str(tmp_path / "loci.db"))
    store.add(
        ids=["a", "b"],
        embeddings=[[1.0] + [0.0] * 767, [0.0, 1.0] + [0.0] * 766],
        texts=["points right", "points up"],
        metadatas=[{"source": "a.txt"}, {"source": "b.txt"}],
    )

    results = store.query(embedding=[0.9, 0.1] + [0.0] * 766, top_k=1)

    assert results[0]["id"] == "a"
    assert results[0]["text"] == "points right"
    assert results[0]["metadata"] == {"source": "a.txt"}


def test_add_with_same_id_updates_instead_of_duplicating(tmp_path):
    store = VectorStore(str(tmp_path / "loci.db"))
    store.add(
        ids=["a"],
        embeddings=[[1.0] + [0.0] * 767],
        texts=["original text"],
        metadatas=[{"source": "a.txt"}],
    )

    store.add(
        ids=["a"],
        embeddings=[[1.0] + [0.0] * 767],
        texts=["updated text"],
        metadatas=[{"source": "a.txt"}],
    )

    results = store.query(embedding=[1.0] + [0.0] * 767, top_k=10)

    assert len(results) == 1
    assert results[0]["text"] == "updated text"


def test_fts5_lexical_match_surfaces_a_result_with_no_dense_neighbor(tmp_path):
    store = VectorStore(str(tmp_path / "loci.db"))
    # "lexical" embedding is orthogonal/far from the query embedding on purpose:
    # only the BM25 side should be able to find it.
    store.add(
        ids=["lexical"],
        embeddings=[[0.0, 0.0, 1.0] + [0.0] * 765],
        texts=["the quick brown fox jumps over the lazy dog"],
        metadatas=[{"source": "fox.txt"}],
    )

    results = store.query(
        embedding=[1.0] + [0.0] * 767,  # nowhere near the stored embedding
        top_k=5,
        query_text="quick brown fox",
    )

    assert any(r["id"] == "lexical" for r in results)


def test_query_without_query_text_still_works_dense_only(tmp_path):
    store = VectorStore(str(tmp_path / "loci.db"))
    store.add(
        ids=["a"],
        embeddings=[[1.0] + [0.0] * 767],
        texts=["points right"],
        metadatas=[{"source": "a.txt"}],
    )

    results = store.query(embedding=[1.0] + [0.0] * 767, top_k=5)

    assert results[0]["id"] == "a"


def test_query_text_with_punctuation_does_not_raise_fts5_syntax_error(tmp_path):
    # Raw natural-language questions contain characters (?, -, *, etc.) that are
    # significant to FTS5's own MATCH query syntax and raise
    # sqlite3.OperationalError: fts5: syntax error if passed through unescaped.
    store = VectorStore(str(tmp_path / "loci.db"))
    store.add(
        ids=["a"],
        embeddings=[[1.0] + [0.0] * 767],
        texts=["the sky is blue on a clear day"],
        metadatas=[{"source": "a.txt"}],
    )

    results = store.query(
        embedding=[1.0] + [0.0] * 767, top_k=5, query_text="What color is the sky?"
    )

    assert any(r["id"] == "a" for r in results)


def test_query_text_with_no_word_tokens_skips_the_sparse_arm(tmp_path):
    # A query_text with no \w tokens (e.g. just punctuation) must not raise and
    # must still return dense-only results.
    store = VectorStore(str(tmp_path / "loci.db"))
    store.add(
        ids=["a"],
        embeddings=[[1.0] + [0.0] * 767],
        texts=["points right"],
        metadatas=[{"source": "a.txt"}],
    )

    results = store.query(embedding=[1.0] + [0.0] * 767, top_k=5, query_text="???")

    assert results[0]["id"] == "a"


def test_rrf_tie_break_is_deterministic_by_ascending_chunk_id(tmp_path):
    # "z" wins the dense arm outright (rank 0, exact embedding match) and never
    # appears in the sparse arm (its text has no overlap with the query text).
    # "s" wins the sparse arm outright (the only chunk containing "zephyr") and
    # is excluded from the dense arm entirely by being ranked worse than
    # fetch_k = max(top_k * 4, top_k) = 4 other, closer chunks. Both therefore
    # score exactly 1 / (RRF_K + 0 + 1) = 1/61 from a single arm each - a
    # genuine tie. Without a deterministic tiebreak, which of the two survives
    # the top_k=1 cutoff depends on Python's (per-process, hash-randomized) set
    # iteration order of {"z", "f1", "f2", "f3", "s"}. The documented tiebreak
    # is ascending chunk_id, and "s" < "z" lexicographically, so "s" must win.
    query_embedding = [1.0] + [0.0] * 767
    store = VectorStore(str(tmp_path / "loci.db"))
    store.add(
        ids=["z", "f1", "f2", "f3", "s"],
        embeddings=[
            [1.0] + [0.0] * 767,  # z: exact match, dense rank 0
            [0.9, 0.1] + [0.0] * 766,  # f1: dense rank 1
            [0.8, 0.2] + [0.0] * 766,  # f2: dense rank 2
            [0.7, 0.3] + [0.0] * 766,  # f3: dense rank 3
            [0.0, 0.0, 1.0] + [0.0] * 765,  # s: farthest, excluded from top-4 dense
        ],
        texts=[
            "points right",
            "points mostly right",
            "points somewhat right",
            "points a little right",
            "the zephyr blows through the canyon",
        ],
        metadatas=[
            {"source": "z.txt"},
            {"source": "f1.txt"},
            {"source": "f2.txt"},
            {"source": "f3.txt"},
            {"source": "s.txt"},
        ],
    )

    for _ in range(5):
        results = store.query(
            embedding=query_embedding, top_k=1, query_text="zephyr"
        )
        assert results[0]["id"] == "s"


def test_init_raises_helpful_error_when_path_is_a_directory(tmp_path):
    leftover_chroma_dir = tmp_path / "chroma_db"
    leftover_chroma_dir.mkdir()

    with pytest.raises(RuntimeError, match="directory"):
        VectorStore(str(leftover_chroma_dir))


def test_chunks_start_at_base_heat_and_touch_on_query(tmp_path):
    store = VectorStore(str(tmp_path / "loci.db"))
    embedding = [1.0, 0.0, 0.0] + [0.0] * 765
    store.add(["c1"], [embedding], ["the sky is blue"], [{}])

    results = store.query(embedding, top_k=1)

    assert results[0]["heat"] == pytest.approx(0.333 + (1 - 0.333) * 0.5)


def test_opening_a_pre_heat_column_database_migrates_it(tmp_path):
    # Simulates a chunk_meta table created before Plan 3 Task 3 added
    # heat/last_used - CREATE TABLE IF NOT EXISTS is a no-op against an
    # existing table with fewer columns, so VectorStore must migrate it
    # explicitly rather than silently fail on the next heat read/write.
    db_path = str(tmp_path / "pre_existing.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE chunk_meta ("
        "chunk_id TEXT PRIMARY KEY, rowid_map INTEGER UNIQUE, "
        "text TEXT NOT NULL, metadata TEXT NOT NULL)"
    )
    conn.commit()
    conn.close()

    store = VectorStore(db_path)
    columns = {row[1] for row in store._conn.execute("PRAGMA table_info(chunk_meta)")}
    assert "heat" in columns
    assert "last_used" in columns

    # And the store must actually be usable afterward, not just have the columns.
    embedding = [1.0, 0.0, 0.0] + [0.0] * 765
    store.add(["c1"], [embedding], ["migrated fine"], [{}])
    results = store.query(embedding, top_k=1)
    assert results[0]["heat"] == pytest.approx(0.333 + (1 - 0.333) * 0.5)
    store.close()


def test_repeated_queries_increase_chunk_heat(tmp_path):
    store = VectorStore(str(tmp_path / "loci.db"))
    embedding = [1.0, 0.0, 0.0] + [0.0] * 765
    store.add(["c1"], [embedding], ["the sky is blue"], [{}])

    first = store.query(embedding, top_k=1)[0]["heat"]
    second = store.query(embedding, top_k=1)[0]["heat"]

    assert second > first
