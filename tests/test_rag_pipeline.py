import pytest

from rag import config
from rag.pipeline import ingest, query

TWO_PAGE_PDF = b"""%PDF-1.4
1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj
2 0 obj<</Type/Pages/Kids[3 0 R 6 0 R]/Count 2>>endobj
3 0 obj<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/MediaBox[0 0 200 200]/Contents 5 0 R>>endobj
4 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj
5 0 obj<</Length 40>>
stream
BT /F1 24 Tf 10 100 Td (Page one text) Tj ET
endstream
endobj
6 0 obj<</Type/Page/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/MediaBox[0 0 200 200]/Contents 7 0 R>>endobj
7 0 obj<</Length 40>>
stream
BT /F1 24 Tf 10 100 Td (Page two text) Tj ET
endstream
endobj
xref
0 8
0000000000 65535 f
trailer<</Size 8/Root 1 0 R>>
startxref
0
%%EOF"""

try:
    import ollama as _ollama_client

    _ollama_client.Client(
        host=config.OLLAMA_HOST, timeout=config.OLLAMA_CONNECT_TIMEOUT_SECONDS
    ).list()
    OLLAMA_AVAILABLE = True
except Exception:
    OLLAMA_AVAILABLE = False

requires_ollama = pytest.mark.skipif(
    not OLLAMA_AVAILABLE, reason="Ollama is not reachable at RAG_OLLAMA_HOST"
)


@pytest.fixture
def isolated_store(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CHROMA_DB_PATH", str(tmp_path / "chroma"))
    return tmp_path


@requires_ollama
def test_ingest_returns_number_of_chunks_added(isolated_store):
    data_dir = isolated_store / "data"
    data_dir.mkdir()
    (data_dir / "note.txt").write_text("The sky is blue on a clear day.")

    count = ingest(str(data_dir))

    assert count == 1


@requires_ollama
def test_ingest_is_idempotent_on_rerun(isolated_store):
    data_dir = isolated_store / "data"
    data_dir.mkdir()
    (data_dir / "note.txt").write_text("The sky is blue on a clear day.")

    ingest(str(data_dir))
    second_count = ingest(str(data_dir))

    from rag.embeddings import embed
    from loci_engine.vectors import VectorStore

    engine = VectorStore(path=config.CHROMA_DB_PATH)
    [query_vector] = embed(["sky"])
    results = engine.query(query_vector, top_k=10)

    assert second_count == 1
    assert len(results) == 1


@requires_ollama
def test_ingest_assigns_distinct_ids_to_chunks_from_different_pdf_pages(isolated_store):
    data_dir = isolated_store / "data"
    data_dir.mkdir()
    (data_dir / "two_page.pdf").write_bytes(TWO_PAGE_PDF)

    # Each page's first chunk gets start_index == 0, so a source+start_index-only
    # id would collide across pages. This must not raise chromadb.errors.DuplicateIDError.
    count = ingest(str(data_dir))

    assert count == 2


@requires_ollama
def test_query_uses_category_adaptive_recall_depth(isolated_store):
    data_dir = isolated_store / "data"
    data_dir.mkdir()
    fruits = [
        "apple", "banana", "cherry", "date", "elderberry", "fig",
        "grape", "honeydew", "kiwi", "lemon", "mango", "nectarine",
    ]
    for fruit in fruits:
        (data_dir / f"{fruit}.txt").write_text(f"{fruit} is a kind of fruit.")
    ingest(str(data_dir))

    info_result = query("What fruit is this?")
    multi_result = query("Summarize and compare all the fruits across the documents")

    assert info_result["category"] == "information_extraction"
    assert info_result["recall_depth"] == 5
    assert multi_result["category"] == "multi_session_reasoning"
    assert multi_result["recall_depth"] == 10
    assert len(multi_result["sources"]) > len(info_result["sources"])


@requires_ollama
def test_query_returns_answer_and_sources(isolated_store):
    data_dir = isolated_store / "data"
    data_dir.mkdir()
    note = data_dir / "note.txt"
    note.write_text("The sky is blue on a clear day.")
    ingest(str(data_dir))

    result = query("What color is the sky?")

    assert isinstance(result["answer"], str)
    assert len(result["answer"]) > 0
    assert str(note) in result["sources"]
