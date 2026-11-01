#!/usr/bin/env python3
"""Tests for the feedback platform — friction = feedback."""
import os
import sys
import tempfile
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import loci_engine.feedback_platform as fp
import loci_engine.glassbox as gb


@pytest.fixture(autouse=True)
def isolated_ledgers(tmp_path, monkeypatch):
    monkeypatch.setattr(fp, "FEEDBACK_PATH", str(tmp_path / "feedback.jsonl"))
    monkeypatch.setattr(gb, "GLASSBOX_PATH", str(tmp_path / "glassbox.jsonl"))
    monkeypatch.setattr(gb, "GLASSBOX_LOCK", str(tmp_path / "glassbox.jsonl.lock"))


def test_submit_and_retrieve():
    entry = fp.submit_feedback(
        author_id="arko",
        category="unification_conflict",
        severity="high",
        title="Laptop engine diverged from workstation",
        description="The console laptop has an older version of the engine that conflicts with the unified architecture.",
        affected_component="loci_engine",
        affected_node="console",
    )
    assert entry["id"].startswith("fb_")
    assert entry["category"] == "unification_conflict"
    assert entry["status"] == "open"

    results = fp.get_feedback(category="unification_conflict")
    assert len(results) == 1
    assert results[0]["title"] == "Laptop engine diverged from workstation"


def test_feedback_visible_in_glassbox():
    fp.submit_feedback(
        author_id="claude_opus",
        category="communication_gap",
        severity="medium",
        title="SSH auth prevents node sync",
        description="Cannot propagate engine to console due to SSH key rejection.",
        affected_node="console",
    )
    entries = gb.glassbox_recall(query="SSH")
    assert len(entries) >= 1
    assert "SSH" in entries[0]["content"]


def test_respond_to_feedback():
    entry = fp.submit_feedback(
        author_id="arko",
        category="auth_barrier",
        severity="high",
        title="SSH keys not set up",
        description="Need ssh-copy-id for laptop and VPS.",
    )
    response = fp.respond_to_feedback(
        feedback_id=entry["id"],
        responder_id="claude_opus",
        response="SSH keys need to be copied interactively. User must run ssh-copy-id.",
        new_status="acknowledged",
    )
    assert response["status"] == "acknowledged"
    assert len(response["responses"]) == 1
    assert response["responses"][0]["responder_id"] == "claude_opus"


def test_feedback_stats():
    fp.submit_feedback(author_id="arko", title="Issue A", description="Desc A", category="node_desync", severity="high")
    fp.submit_feedback(author_id="arko", title="Issue B", description="Desc B", category="node_desync", severity="low")
    fp.submit_feedback(author_id="claude", title="Issue C", description="Desc C", category="performance_issue", severity="critical")

    stats = fp.feedback_stats()
    assert stats["total"] == 3
    assert stats["by_category"]["node_desync"] == 2
    assert stats["by_severity"]["critical"] == 1
    assert stats["open_high_priority"] == 2  # high + critical


def test_filter_by_node():
    fp.submit_feedback(author_id="arko", title="WS issue", description="D", affected_node="workstation")
    fp.submit_feedback(author_id="arko", title="Console issue", description="D", affected_node="console")
    fp.submit_feedback(author_id="arko", title="VPS issue", description="D", affected_node="vps")

    console = fp.get_feedback(node="console")
    assert len(console) == 1
    assert console[0]["affected_node"] == "console"


def test_severity_filter():
    fp.submit_feedback(author_id="arko", title="Critical", description="D", severity="critical")
    fp.submit_feedback(author_id="arko", title="Info", description="D", severity="info")

    critical = fp.get_feedback(severity="critical")
    assert len(critical) == 1
    assert critical[0]["severity"] == "critical"
