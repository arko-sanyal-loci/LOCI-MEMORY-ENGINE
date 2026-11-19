import pytest

from rag import config
from rag.llm import generate

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
def test_generate_returns_nonempty_answer():
    answer = generate("Reply with exactly one word: hello")

    assert isinstance(answer, str)
    assert len(answer.strip()) > 0


def test_generate_defaults_to_compact_role_and_uses_compact_host(monkeypatch):
    monkeypatch.setattr(config, "COMPACT_HOST", "http://127.0.0.1:1")
    monkeypatch.setattr(config, "OLLAMA_CONNECT_TIMEOUT_SECONDS", 1.0)

    with pytest.raises(ConnectionError, match="ollama serve"):
        generate("test")


def test_generate_raises_clear_error_when_ollama_unreachable(monkeypatch):
    monkeypatch.setattr(config, "COMPACT_HOST", "http://127.0.0.1:1")
    monkeypatch.setattr(config, "OLLAMA_CONNECT_TIMEOUT_SECONDS", 1.0)

    with pytest.raises(ConnectionError, match="ollama serve"):
        generate("test")


def test_generate_uses_separate_connect_and_read_timeouts(monkeypatch):
    monkeypatch.setattr(config, "OLLAMA_CONNECT_TIMEOUT_SECONDS", 3.0)
    monkeypatch.setattr(config, "GENERATE_TIMEOUT_SECONDS", 90.0)
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"choices": [{"message": {"content": "ok"}}]}

    def fake_post(url, json, timeout):
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("rag.llm.httpx.post", fake_post)

    generate("test")

    assert captured["timeout"].connect == 3.0
    assert captured["timeout"].read == 90.0


def test_generate_rejects_unknown_role():
    with pytest.raises(ValueError, match="compact"):
        generate("test", role="bogus")


def test_generate_raises_clear_error_when_expand_lane_not_configured(monkeypatch):
    monkeypatch.setattr(config, "EXPAND_HOST", None)
    monkeypatch.setattr(config, "EXPAND_MODEL", None)

    with pytest.raises(ConnectionError, match="expand"):
        generate("test", role="expand")


def test_generate_uses_expand_host_and_model_when_configured(monkeypatch):
    monkeypatch.setattr(config, "EXPAND_HOST", "http://127.0.0.1:1")
    monkeypatch.setattr(config, "EXPAND_MODEL", "qwen3-coder-30b")
    monkeypatch.setattr(config, "OLLAMA_CONNECT_TIMEOUT_SECONDS", 1.0)

    with pytest.raises(ConnectionError, match="llama-server"):
        generate("test", role="expand")
