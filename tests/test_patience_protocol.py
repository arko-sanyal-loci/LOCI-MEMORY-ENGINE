#!/usr/bin/env python3
"""Tests for the patience protocol — trajectory awareness, patience scoring, escalation chain."""
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import loci_engine.glassbox as gb
from loci_engine.patience_protocol import (
    detect_trajectory,
    compute_patience_score,
    get_enrollment_display,
    escalate_block,
    BYPASS_SEVERITIES,
    PATIENCE_PRINCIPLES,
)


@pytest.fixture(autouse=True)
def isolated_glassbox(tmp_path, monkeypatch):
    monkeypatch.setattr(gb, "GLASSBOX_PATH", str(tmp_path / "glassbox.jsonl"))
    monkeypatch.setattr(gb, "GLASSBOX_LOCK", str(tmp_path / "glassbox.jsonl.lock"))


def _build_history(component: str, count: int, gap_s: float = 30.0) -> list:
    """Generate a sequential action history on one component."""
    now = time.time()
    return [
        {
            "action_type": "file_write",
            "component": component,
            "timestamp": now - (count - i) * gap_s,
            "actor_id": "arko",
        }
        for i in range(count)
    ]


def test_trajectory_detected_mid_build():
    history = _build_history("session_continuity", 5)
    result = detect_trajectory(history)
    assert result["trajectory_detected"] is True
    assert result["confidence"] > 0.6
    assert result["active_component"] == "session_continuity"
    assert result["patience_multiplier"] > 1.0


def test_no_trajectory_with_single_action():
    history = [{"action_type": "file_write", "component": "random", "timestamp": time.time(), "actor_id": "arko"}]
    result = detect_trajectory(history)
    assert result["trajectory_detected"] is False
    assert result["confidence"] == 0.0


def test_patience_high_for_mid_build():
    history = _build_history("loci_engine", 6)
    decision = compute_patience_score(
        proposed_intervention={"severity": "medium", "reason": "code style concern", "reversible": True, "target_component": "loci_engine"},
        action_history=history,
    )
    assert decision["patience_score"] > 0.7
    assert decision["action"] == "wait"


def test_patience_low_for_emergency():
    history = _build_history("database", 3)
    decision = compute_patience_score(
        proposed_intervention={"severity": "data_destruction", "reason": "rm -rf /", "reversible": False},
        action_history=history,
    )
    assert decision["patience_score"] == 0.0
    assert decision["action"] == "intervene"


def test_patience_medium_for_high_severity():
    decision = compute_patience_score(
        proposed_intervention={"severity": "high", "reason": "potential security issue", "reversible": True},
        action_history=[],
    )
    assert decision["patience_score"] < 0.7
    assert decision["action"] in ("alert", "feedback")


def test_reversible_increases_patience():
    base = compute_patience_score(
        proposed_intervention={"severity": "medium", "reason": "test", "reversible": False},
        action_history=[],
    )
    reversible = compute_patience_score(
        proposed_intervention={"severity": "medium", "reason": "test", "reversible": True},
        action_history=[],
    )
    assert reversible["patience_score"] > base["patience_score"]


def test_enrollment_display():
    enrollment = get_enrollment_display()
    assert len(enrollment["principles"]) == len(PATIENCE_PRINCIPLES)
    assert "guidance" in enrollment["note"].lower()
    assert enrollment["default_action"] == "wait"


def test_escalation_chain():
    result = escalate_block(
        blocker_agent_id="auto_mode_classifier",
        blocked_agent_id="claude_opus",
        block_reason="Safety Bypass Flag detected",
        feedback_reason="This was a standard pip install needed for testing",
        affected_component="package_management",
    )
    assert result["escalation_id"].startswith("esc_")
    assert result["block_reason"] == "Safety Bypass Flag detected"
    assert result["feedback_reason"] == "This was a standard pip install needed for testing"
    assert result["next_step"] == "research_loop"
    assert len(result["chain"]) == 6

    # Verify both reasons logged to Glassbox
    entries = gb.glassbox_recall(query="BLOCK")
    assert len(entries) >= 1
    entries = gb.glassbox_recall(query="FEEDBACK on BLOCK")
    assert len(entries) >= 1


def test_guidance_generated():
    history = _build_history("mcp_server", 4)
    decision = compute_patience_score(
        proposed_intervention={"severity": "low", "reason": "naming convention", "reversible": True, "target_component": "mcp_server"},
        action_history=history,
    )
    assert "guidance" in decision
    assert len(decision["guidance"]) > 0
