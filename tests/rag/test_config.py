import importlib

import pytest

from rag import config


@pytest.fixture(autouse=True)
def _reload_config_after_test():
    # config.py reads env vars at import time; importlib.reload() mutates the one
    # shared module object every other test file's `from rag import config` sees.
    # Reload once more after each test, with no test-specific env vars set, so a
    # later test file doesn't inherit this file's reload-time environment.
    yield
    importlib.reload(config)


def test_compact_and_embedding_default_to_the_existing_ollama_host(monkeypatch):
    monkeypatch.delenv("RAG_COMPACT_HOST", raising=False)
    monkeypatch.delenv("RAG_EMBEDDING_HOST", raising=False)
    monkeypatch.delenv("RAG_COMPACT_MODEL", raising=False)
    monkeypatch.setenv("RAG_OLLAMA_HOST", "http://127.0.0.1:11434")
    monkeypatch.setenv("RAG_LLM_MODEL", "llama3.2")

    reloaded = importlib.reload(config)

    assert reloaded.COMPACT_HOST == reloaded.OLLAMA_HOST == "http://127.0.0.1:11434"
    assert reloaded.EMBEDDING_HOST == reloaded.OLLAMA_HOST
    assert reloaded.COMPACT_MODEL == reloaded.LLM_MODEL == "llama3.2"


def test_compact_host_can_be_overridden_independently_of_ollama_host(monkeypatch):
    monkeypatch.setenv("RAG_OLLAMA_HOST", "http://127.0.0.1:11434")
    monkeypatch.setenv("RAG_COMPACT_HOST", "http://127.0.0.1:11500")

    reloaded = importlib.reload(config)

    assert reloaded.COMPACT_HOST == "http://127.0.0.1:11500"
    assert reloaded.OLLAMA_HOST == "http://127.0.0.1:11434"


def test_expand_host_and_model_have_no_default(monkeypatch):
    monkeypatch.delenv("RAG_EXPAND_HOST", raising=False)
    monkeypatch.delenv("RAG_EXPAND_MODEL", raising=False)

    reloaded = importlib.reload(config)

    assert reloaded.EXPAND_HOST is None
    assert reloaded.EXPAND_MODEL is None


def test_generate_timeout_defaults_and_is_independent_of_connect_timeout(monkeypatch):
    monkeypatch.delenv("RAG_GENERATE_TIMEOUT_SECONDS", raising=False)
    monkeypatch.setenv("RAG_OLLAMA_CONNECT_TIMEOUT_SECONDS", "1")

    reloaded = importlib.reload(config)

    assert reloaded.GENERATE_TIMEOUT_SECONDS == 120.0
    assert reloaded.OLLAMA_CONNECT_TIMEOUT_SECONDS == 1.0


def test_generate_timeout_reads_from_environment(monkeypatch):
    monkeypatch.setenv("RAG_GENERATE_TIMEOUT_SECONDS", "45")

    reloaded = importlib.reload(config)

    assert reloaded.GENERATE_TIMEOUT_SECONDS == 45.0


def test_expand_host_and_model_read_from_environment(monkeypatch):
    monkeypatch.setenv("RAG_EXPAND_HOST", "http://127.0.0.1:8080")
    monkeypatch.setenv("RAG_EXPAND_MODEL", "qwen2.5-coder-32b")

    reloaded = importlib.reload(config)

    assert reloaded.EXPAND_HOST == "http://127.0.0.1:8080"
    assert reloaded.EXPAND_MODEL == "qwen2.5-coder-32b"
