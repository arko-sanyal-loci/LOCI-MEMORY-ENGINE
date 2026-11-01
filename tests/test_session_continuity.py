#!/usr/bin/env python3
"""Tests for cross-session continuity: LDCE tiers, session lifecycle, PRS."""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from loci_engine.storage import StorageEngine
from loci_engine.session_continuity import (
    start_session,
    end_session,
    compute_ldce_tiers,
    inject_context,
    record_recall,
    get_session_history,
    get_prs_trend,
    KERNEL_HEAT_THRESHOLD,
    HOP_HEAT_THRESHOLD,
)


@pytest.fixture
def engine(tmp_path):
    db_path = str(tmp_path / "test_session.db")
    eng = StorageEngine(db_path=db_path)
    # Seed some facts at different heat levels
    eng.insert_fact("hot_1", "test", "This is a hot fact", heat=0.95)
    eng.insert_fact("hot_2", "test", "Another hot fact", heat=0.80)
    eng.insert_fact("hot_3", "test", "Third hot fact", heat=0.70)
    eng.insert_fact("mild_1", "test", "A mild fact", heat=0.30)
    eng.insert_fact("mild_2", "test", "Another mild fact", heat=0.25)
    eng.insert_fact("cold_1", "test", "A cold fact", heat=0.10)
    eng.insert_fact("cold_2", "test", "Barely there fact", heat=0.05)
    # Seed ethics principles
    eng.insert_fact("eth_1", "ethics.core", "Comprehension is always free", heat=1.0)
    eng.insert_fact("eth_2", "ethics.core", "Empathy is predictive", heat=1.0)
    return eng


def test_ldce_tier_assignment(engine):
    tiers = compute_ldce_tiers(engine)
    assert "kernel" in tiers
    assert "hop" in tiers
    assert "offload" in tiers
    # Hot items should be in kernel
    kernel_ids = [item["id"] for item in tiers["kernel"]]
    assert "hot_1" in kernel_ids
    assert "eth_1" in kernel_ids  # ethics at heat=1.0
    # Cold items should not be in kernel
    assert "cold_1" not in kernel_ids
    assert "cold_2" not in kernel_ids
    # Stats should be present
    assert tiers["stats"]["kernel_count"] > 0
    assert tiers["stats"]["context_token_estimate"] > 0


def test_session_lifecycle(engine):
    # Start a session
    session = start_session(engine, agent_id="test_agent")
    assert session["session_id"].startswith("sess_")
    assert session["agent_id"] == "test_agent"
    assert session["ldce"]["stats"]["kernel_count"] > 0

    # End the session
    result = end_session(engine, session["session_id"])
    assert result["status"] == "completed"
    assert result["ended_at"] is not None


def test_session_bridging(engine):
    # Start and end first session
    s1 = start_session(engine, agent_id="test_agent")
    end_session(engine, s1["session_id"])

    # Bridge to second session
    s2 = start_session(engine, agent_id="test_agent", bridge_from_session=s1["session_id"])
    assert s2["bridged_from"] == s1["session_id"]


def test_ethics_enrollment_at_session_start(engine):
    session = start_session(engine, agent_id="test_agent")
    # LDCE should include ethics items in kernel (heat=1.0)
    kernel_items = session["ldce"]["kernel"]
    ethics_in_kernel = [item for item in kernel_items if item["namespace"].startswith("ethics")]
    assert len(ethics_in_kernel) >= 2


def test_prs_computation(engine):
    # Start session 1, log some recalls
    s1 = start_session(engine, agent_id="test_agent")
    record_recall(engine, s1["session_id"], "hot_1", "kernel", 0.95)
    record_recall(engine, s1["session_id"], "hot_2", "kernel", 0.80)
    record_recall(engine, s1["session_id"], "mild_1", "hop", 0.30)
    end_session(engine, s1["session_id"])

    # Start session 2 bridged from session 1
    s2 = start_session(engine, agent_id="test_agent", bridge_from_session=s1["session_id"])
    # Recall some items from prior session
    record_recall(engine, s2["session_id"], "hot_1", "kernel", 0.93)
    record_recall(engine, s2["session_id"], "hot_2", "hop", 0.75)
    result = end_session(engine, s2["session_id"])
    # PRS should be computed (> 0 since we recalled items from prior)
    assert result["prs_score"] is not None
    assert result["prs_score"] >= 0.0


def test_session_history(engine):
    s1 = start_session(engine, agent_id="agent_a")
    end_session(engine, s1["session_id"])
    s2 = start_session(engine, agent_id="agent_b")
    end_session(engine, s2["session_id"])

    history = get_session_history(engine)
    assert len(history) >= 2

    history_a = get_session_history(engine, agent_id="agent_a")
    assert all(h["agent_id"] == "agent_a" for h in history_a)


def test_inject_context(engine):
    session = start_session(engine, agent_id="test_agent")
    kernel = inject_context(engine, session["session_id"], tier="kernel")
    assert isinstance(kernel, list)
    assert len(kernel) > 0
    # All kernel items should have heat >= threshold
    for item in kernel:
        assert item["heat"] >= KERNEL_HEAT_THRESHOLD


def test_expired_sessions_cleaned(engine):
    # Start two sessions for same agent — first should expire
    s1 = start_session(engine, agent_id="test_agent")
    s2 = start_session(engine, agent_id="test_agent")
    history = get_session_history(engine, agent_id="test_agent")
    statuses = [h["status"] for h in history]
    assert "expired" in statuses
    assert "active" in statuses
