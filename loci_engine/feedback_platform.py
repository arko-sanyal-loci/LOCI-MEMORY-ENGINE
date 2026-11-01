#!/usr/bin/env python3
"""
LOCI Feedback Platform — Friction = Feedback

Per Arko's principle: friction is feedback, not opposition. Every point of
friction in the system — between agents, between nodes, between sessions —
is a signal worth capturing, understanding, and learning from.

This is the structured feedback system that:
1. Captures friction/feedback from any agent or human
2. Routes it through the Glassbox for transparency
3. Tracks resolution and response
4. Aggregates patterns so the system learns from its own friction

Deployable on both the local subnet and billo.tech VPS.
No hidden channels — all feedback visible in the Glassbox.
"""

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loci_engine.glassbox import glassbox_learn, glassbox_recall

FEEDBACK_PATH = os.getenv(
    "LOCI_FEEDBACK_PATH",
    os.path.expanduser("~/loci-memory-engine/feedback_ledger.jsonl"),
)

FRICTION_CATEGORIES = [
    "unification_conflict",   # diverging engines, merge friction
    "protocol_violation",     # unification protocol not followed
    "communication_gap",      # agents not communicating clearly
    "ethical_concern",        # ethics/principles not being followed
    "resource_contention",    # GPU/memory/network contention
    "session_discontinuity",  # cross-session continuity failure
    "node_desync",            # nodes out of sync
    "auth_barrier",           # authentication/access friction
    "performance_issue",      # speed/latency friction
    "missing_capability",     # something needed but not built
    "ux_friction",            # user experience friction
    "general",                # catch-all
]

SEVERITY_LEVELS = ["info", "low", "medium", "high", "critical"]

STATUS_FLOW = ["open", "acknowledged", "investigating", "resolved", "wont_fix"]


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_feedback() -> List[Dict[str, Any]]:
    if not os.path.exists(FEEDBACK_PATH):
        return []
    entries = []
    with open(FEEDBACK_PATH, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def submit_feedback(
    author_id: str,
    category: str = "general",
    severity: str = "medium",
    title: str = "",
    description: str = "",
    affected_component: str = "",
    affected_node: str = "",
    reproduction_steps: str = "",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Submit a friction/feedback report. Every submission is logged to
    both the feedback ledger and the Glassbox for full transparency.

    Friction categories map to specific system concerns — they tell
    the system WHERE the friction is, not just that it exists.
    """
    feedback_id = f"fb_{uuid.uuid4().hex[:12]}"
    now = _utc_iso()

    if category not in FRICTION_CATEGORIES:
        category = "general"
    if severity not in SEVERITY_LEVELS:
        severity = "medium"

    entry = {
        "id": feedback_id,
        "timestamp": now,
        "author_id": author_id,
        "category": category,
        "severity": severity,
        "title": title,
        "description": description,
        "affected_component": affected_component,
        "affected_node": affected_node,
        "reproduction_steps": reproduction_steps,
        "status": "open",
        "responses": [],
        "metadata": metadata or {},
    }

    with open(FEEDBACK_PATH, "a") as f:
        f.write(json.dumps(entry, separators=(",", ":")) + "\n")

    # Log to Glassbox for transparency
    glassbox_content = (
        f"[FEEDBACK:{severity.upper()}] {title}\n"
        f"Category: {category} | Component: {affected_component or 'unspecified'}\n"
        f"Node: {affected_node or 'any'}\n"
        f"{description}"
    )
    glassbox_learn(
        author_id=author_id,
        role_tag="feedback_platform",
        content=glassbox_content,
        category="warning" if severity in ("high", "critical") else "observation",
        metadata={"feedback_id": feedback_id, "severity": severity},
    )

    return entry


def get_feedback(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    author_id: Optional[str] = None,
    node: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Retrieve feedback entries with optional filters."""
    entries = _read_feedback()

    if category:
        entries = [e for e in entries if e.get("category") == category]
    if severity:
        entries = [e for e in entries if e.get("severity") == severity]
    if status:
        entries = [e for e in entries if e.get("status") == status]
    if author_id:
        entries = [e for e in entries if e.get("author_id") == author_id]
    if node:
        entries = [e for e in entries if e.get("affected_node") == node]

    return entries[-limit:]


def respond_to_feedback(
    feedback_id: str,
    responder_id: str,
    response: str,
    new_status: Optional[str] = None,
) -> Dict[str, Any]:
    """Respond to a feedback entry. Responses are appended (never replace).
    Status can be updated as part of the response.
    """
    entries = _read_feedback()
    found = None
    found_idx = None

    for idx, e in enumerate(entries):
        if e.get("id") == feedback_id:
            found = e
            found_idx = idx
            break

    if not found:
        return {"error": f"feedback {feedback_id} not found"}

    resp = {
        "responder_id": responder_id,
        "response": response,
        "timestamp": _utc_iso(),
    }
    found["responses"].append(resp)

    if new_status and new_status in STATUS_FLOW:
        found["status"] = new_status

    # Rewrite ledger with updated entry
    with open(FEEDBACK_PATH, "w") as f:
        for e in entries:
            f.write(json.dumps(e, separators=(",", ":")) + "\n")

    # Log response to Glassbox
    glassbox_learn(
        author_id=responder_id,
        role_tag="feedback_response",
        content=f"[RESPONSE to {feedback_id}] {response}",
        category="correction" if new_status == "resolved" else "observation",
        metadata={"feedback_id": feedback_id, "new_status": new_status},
    )

    return found


def feedback_stats() -> Dict[str, Any]:
    """Aggregate feedback statistics — shows where friction concentrates."""
    entries = _read_feedback()
    if not entries:
        return {"total": 0, "by_category": {}, "by_severity": {}, "by_status": {}, "by_node": {}}

    by_category: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    by_status: Dict[str, int] = {}
    by_node: Dict[str, int] = {}

    for e in entries:
        cat = e.get("category", "general")
        sev = e.get("severity", "medium")
        st = e.get("status", "open")
        node = e.get("affected_node", "unspecified") or "unspecified"

        by_category[cat] = by_category.get(cat, 0) + 1
        by_severity[sev] = by_severity.get(sev, 0) + 1
        by_status[st] = by_status.get(st, 0) + 1
        by_node[node] = by_node.get(node, 0) + 1

    open_high = len([e for e in entries if e.get("status") == "open" and e.get("severity") in ("high", "critical")])

    return {
        "total": len(entries),
        "open_high_priority": open_high,
        "by_category": by_category,
        "by_severity": by_severity,
        "by_status": by_status,
        "by_node": by_node,
        "first_feedback": entries[0].get("timestamp"),
        "latest_feedback": entries[-1].get("timestamp"),
    }
