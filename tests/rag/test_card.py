from rag.card import RECALL_DEPTH, apply_ranking_strategy, classify_query_category


def test_classify_defaults_to_information_extraction():
    assert classify_query_category("What is the capital of France?") == "information_extraction"


def test_classify_detects_knowledge_update():
    assert classify_query_category("What is the current status of the project now?") == "knowledge_update"


def test_classify_detects_temporal_reasoning():
    assert classify_query_category("What is the history of this feature?") == "temporal_reasoning"


def test_classify_detects_multi_session_reasoning():
    assert classify_query_category("Summarize and compare findings across all the papers") == "multi_session_reasoning"


def test_recall_depth_matches_card_paper_table():
    assert RECALL_DEPTH["information_extraction"] == 5
    assert RECALL_DEPTH["knowledge_update"] == 3
    assert RECALL_DEPTH["multi_session_reasoning"] == 10
    assert RECALL_DEPTH["temporal_reasoning"] == 7


def test_apply_ranking_strategy_orders_knowledge_update_by_heat_descending():
    results = [
        {"text": "cold", "heat": 0.1},
        {"text": "hot", "heat": 0.6},
        {"text": "mild", "heat": 0.3},
    ]

    ordered = apply_ranking_strategy("knowledge_update", results)

    assert [r["text"] for r in ordered] == ["hot", "mild", "cold"]


def test_apply_ranking_strategy_knowledge_update_ties_break_by_recency():
    results = [
        {"text": "older", "heat": 0.5, "metadata": {"moddate": "2026-01-01"}},
        {"text": "newer", "heat": 0.5, "metadata": {"moddate": "2026-06-01"}},
    ]

    ordered = apply_ranking_strategy("knowledge_update", results)

    assert [r["text"] for r in ordered] == ["newer", "older"]


def test_apply_ranking_strategy_orders_temporal_reasoning_chronologically():
    results = [
        {"text": "third", "metadata": {"creationdate": "2026-06-01T00:00:00-00:00"}},
        {"text": "first", "metadata": {"creationdate": "2026-01-01T00:00:00-00:00"}},
        {"text": "second", "metadata": {"creationdate": "2026-03-01T00:00:00-00:00"}},
    ]

    ordered = apply_ranking_strategy("temporal_reasoning", results)

    assert [r["text"] for r in ordered] == ["first", "second", "third"]


def test_apply_ranking_strategy_leaves_other_categories_unchanged():
    results = [
        {"text": "b", "metadata": {}},
        {"text": "a", "metadata": {}},
    ]

    ordered = apply_ranking_strategy("information_extraction", results)

    assert [r["text"] for r in ordered] == ["b", "a"]


def test_apply_ranking_strategy_knowledge_update_tolerates_missing_heat():
    results = [
        {"text": "no-heat", "metadata": {}},
        {"text": "has-heat", "heat": 0.4, "metadata": {}},
    ]

    ordered = apply_ranking_strategy("knowledge_update", results)

    assert len(ordered) == 2


def test_hybrid_ranking_prefers_user_ground_truth_before_heat():
    results = [
        {"text": "inferred-hot", "heat": 0.9, "metadata": {}},
        {
            "text": "user-ground-truth",
            "heat": 0.1,
            "metadata": {"provenance": "user_stated"},
        },
    ]

    ordered = apply_ranking_strategy("information_extraction", results)

    assert [r["text"] for r in ordered] == ["user-ground-truth", "inferred-hot"]


def test_hybrid_ranking_uses_trs_stream_score_after_ground_truth():
    results = [
        {
            "text": "weak-stream",
            "heat": 0.9,
            "metadata": {"trs_final_package": {"streams": {"I": {"score": 0.1}}}},
        },
        {
            "text": "strong-stream",
            "heat": 0.1,
            "metadata": {"trs_final_package": {"streams": {"I": {"score": 0.8}}}},
        },
    ]

    ordered = apply_ranking_strategy("multi_session_reasoning", results)

    assert [r["text"] for r in ordered] == ["strong-stream", "weak-stream"]


def test_temporal_hybrid_keeps_chronology_when_signals_match():
    results = [
        {"text": "later", "metadata": {"creationdate": "2026-06-01"}},
        {"text": "earlier", "metadata": {"creationdate": "2026-01-01"}},
    ]

    ordered = apply_ranking_strategy("temporal_reasoning", results)

    assert [r["text"] for r in ordered] == ["earlier", "later"]
