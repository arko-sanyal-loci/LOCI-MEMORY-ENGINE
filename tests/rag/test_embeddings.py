import pytest

from rag import config
from rag.embeddings import embed

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


@requires_ollama
def test_embed_returns_one_vector_per_input_text():
    vectors = embed(["hello world"])

    assert len(vectors) == 1
    assert len(vectors[0]) > 0
    assert all(isinstance(x, float) for x in vectors[0])


@requires_ollama
def test_embed_produces_distinct_vectors_for_distinct_texts():
    vectors = embed(["the cat sat on the mat", "quantum mechanics and relativity"])

    assert vectors[0] != vectors[1]


def test_embed_raises_clear_error_when_ollama_unreachable(monkeypatch):
    monkeypatch.setattr(config, "EMBEDDING_HOST", "http://127.0.0.1:1")
    monkeypatch.setattr(config, "OLLAMA_CONNECT_TIMEOUT_SECONDS", 1.0)

    with pytest.raises(ConnectionError, match="ollama serve"):
        embed(["test"])
