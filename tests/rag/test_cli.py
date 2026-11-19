from rag import cli


def test_main_ingest_calls_pipeline_ingest_and_prints_count(monkeypatch, capsys):
    monkeypatch.setattr(cli.pipeline, "ingest", lambda data_dir=None: 5)

    exit_code = cli.main(["ingest"])

    assert exit_code == 0
    assert "5" in capsys.readouterr().out


def test_main_ingest_passes_data_dir_argument(monkeypatch, capsys):
    captured = {}
    monkeypatch.setattr(
        cli.pipeline, "ingest", lambda data_dir=None: captured.setdefault("data_dir", data_dir) or 1
    )

    cli.main(["ingest", "--data-dir", "/tmp/some-docs"])

    assert captured["data_dir"] == "/tmp/some-docs"


def test_main_query_prints_answer_and_sources(monkeypatch, capsys):
    monkeypatch.setattr(
        cli.pipeline,
        "query",
        lambda question, top_k=None: {"answer": "Paris.", "sources": ["a.txt", "b.txt"]},
    )

    exit_code = cli.main(["query", "What is the capital of France?"])

    out = capsys.readouterr().out
    assert exit_code == 0
    assert "Paris." in out
    assert "a.txt" in out
    assert "b.txt" in out


def test_main_query_defaults_top_k_to_none_so_card_can_auto_classify(monkeypatch):
    captured = {}

    def fake_query(question, top_k=None):
        captured["top_k"] = top_k
        return {"answer": "x", "sources": []}

    monkeypatch.setattr(cli.pipeline, "query", fake_query)

    cli.main(["query", "What is the capital of France?"])

    assert captured["top_k"] is None


def test_main_query_passes_through_explicit_top_k(monkeypatch):
    captured = {}

    def fake_query(question, top_k=None):
        captured["top_k"] = top_k
        return {"answer": "x", "sources": []}

    monkeypatch.setattr(cli.pipeline, "query", fake_query)

    cli.main(["query", "What is the capital of France?", "--top-k", "8"])

    assert captured["top_k"] == 8


def test_main_reports_clear_error_instead_of_crashing(monkeypatch, capsys):
    def raise_missing(data_dir=None):
        raise FileNotFoundError("No documents found in ./data.")

    monkeypatch.setattr(cli.pipeline, "ingest", raise_missing)

    exit_code = cli.main(["ingest"])

    assert exit_code == 1
    assert "No documents found" in capsys.readouterr().err
