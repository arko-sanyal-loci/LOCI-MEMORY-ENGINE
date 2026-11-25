"""Offline end-to-end pass: ingest → chunk → embed → store → heat → retrieve → gate → compress → answer.

Ollama is replaced by a deterministic bag-of-words embedder and an echo
generator, so this runs in CI with no model server. Everything else (loader,
chunker, sqlite-vec + FTS5 store, CARD routing, heat reinforcement, τ gate,
TF-IDF compressor) is the real code.
"""
import hashlib
import math
import re

import pytest

pytest.importorskip("sqlite_vec")
pytest.importorskip("langchain_text_splitters")

from loci_engine.vectors import EMBEDDING_DIM, VectorStore
from rag import config, pipeline

DOCS = {
    "heat.txt": (
        "The LOCI heat law decays memory hyperbolically. "
        "Facts above the HOT boundary of 0.70 are admitted to the working set. "
        "Heat never reaches zero because of the alpha floor of 0.05."
    ),
    "garden.txt": (
        "Tomatoes need six hours of sun. Water them in the morning. "
        "Basil grows well next to tomatoes and keeps pests away."
    ),
    "bus.txt": (
        "The value bus forwards only committed values between agents. "
        "A slot moves from declared to proposed to committed."
    ),
}


def fake_embed(texts):
    out = []
    for t in texts:
        v = [0.0] * EMBEDDING_DIM
        for w in re.findall(r"[a-z0-9.]+", t.lower()):
            v[int(hashlib.md5(w.encode()).hexdigest(), 16) % EMBEDDING_DIM] += 1.0
        n = math.sqrt(sum(x * x for x in v)) or 1.0
        out.append([x / n for x in v])
    return out


@pytest.fixture
def offline(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    for name, text in DOCS.items():
        (data / name).write_text(text)
    db = tmp_path / "rag.db"
    prompts = []
    monkeypatch.setattr(config, "DB_PATH", str(db))
    monkeypatch.setattr(config, "DATA_DIR", str(data))
    monkeypatch.setattr(pipeline, "embed", fake_embed)
    monkeypatch.setattr(pipeline, "generate", lambda p: prompts.append(p) or "ANSWER")
    return {"db": str(db), "data": str(data), "prompts": prompts}


def test_ingest_then_query_returns_relevant_source(offline):
    n = pipeline.ingest()
    assert n >= 3
    # Re-ingest is idempotent (chunk ids are content-addressed).
    assert pipeline.ingest() == n
    store = VectorStore(path=offline["db"])
    try:
        assert store.count() == n
    finally:
        store.close()

    res = pipeline.query("What is the HOT boundary in the LOCI heat law?", top_k=1)
    assert res["answer"] == "ANSWER"
    assert any(s.endswith("heat.txt") for s in res["sources"])
    assert set(res["gate"]) >= {"tau", "passed"}
    assert "0.70" in offline["prompts"][-1]


def _heats(db):
    store = VectorStore(path=db)
    try:
        return dict(store._conn.execute("SELECT chunk_id, heat FROM chunk_meta").fetchall())
    finally:
        store.close()


def test_retrieval_reinforces_heat(offline):
    pipeline.ingest()
    before = _heats(offline["db"])
    pipeline.query("value bus committed slot", top_k=1)
    after = _heats(offline["db"])
    raised = [k for k in before if after[k] > before[k]]
    assert raised, "the retrieved chunk should be reinforced"
    assert all(0.05 <= h < 1.0 for h in after.values())  # open interval, alpha floor


def test_multi_session_query_expands_adjacent_chunks_with_provenance(offline):
    store = VectorStore(path=offline["db"])
    texts = [
        "Earlier notes mention a Billo Tech identity context.",
        "Billo Microsoft tenant setup requires domain DNS verification.",
        "The adjacent note says to record the tenant ID after setup.",
    ]
    vectors = fake_embed(texts)
    store.add(
        ids=["prev", "tenant", "next"],
        embeddings=vectors,
        texts=texts,
        metadatas=[
            {"source": "m365-notes.txt", "page": 0, "start_index": 0},
            {"source": "m365-notes.txt", "page": 0, "start_index": 100},
            {"source": "m365-notes.txt", "page": 0, "start_index": 200},
        ],
    )
    store.close()

    result = pipeline.query("Summarize Billo Microsoft tenant setup across notes", top_k=1)

    assert result["category"] == "multi_session_reasoning"
    assert result["neighbor_count"] == 2
    assert result["context_count"] == 3
    prompt = offline["prompts"][-1]
    assert "relation=adjacent_chunk" in prompt
    assert "tenant ID after setup" in prompt
    assert "m365-notes.txt" in prompt


def test_abstain_and_compression_flags(offline, monkeypatch):
    pipeline.ingest()
    monkeypatch.setattr(config, "COMPRESS_RATIO", 2.0)
    res = pipeline.query("Which plant grows well next to tomatoes?", top_k=3)
    assert res["compression"] is not None
    assert res["compression"]["compressed_tokens"] <= res["compression"]["original_tokens"]

    monkeypatch.setattr(config, "COMPRESS_RATIO", 0.0)
    monkeypatch.setattr(config, "ABSTAIN_ON_GATE", True)
    res = pipeline.query("zzqx unrelated quantum lattice", top_k=3)
    if not res["gate"]["passed"]:
        assert res["answer"] == pipeline.ABSTAIN_ANSWER
        assert res["sources"] == []


def test_ingest_empty_dir_is_an_explicit_error(offline, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        pipeline.ingest(str(empty))
