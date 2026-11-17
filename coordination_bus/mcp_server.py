"""MCP service exposing the secure LOCI coordination bus to coding agents.

The MCP process binds one agent identity at startup. Agents never submit their
own identity, secret, project scope, or permissions as tool arguments. Those
values come from the host environment and are enforced by SecureEventBus.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, TypeVar

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore[assignment,misc]

from .bus import AgentPolicy, AuthorizationError, CoordinationError, SecureEventBus, TaskBoard

F = TypeVar("F", bound=Callable[..., Any])


@dataclass
class CoordinationRuntime:
    agent_id: str
    bus: SecureEventBus
    board: TaskBoard
    projects: frozenset[str]
    operations: frozenset[str]
    reviewer: bool


def _csv(name: str) -> frozenset[str]:
    items = frozenset(item.strip() for item in os.environ.get(name, "").split(",") if item.strip())
    if not items:
        raise RuntimeError(f"{name} must contain at least one value")
    return items


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def _load_runtime() -> CoordinationRuntime:
    agent_id = os.environ.get("LOCI_AGENT_ID", "").strip()
    secret = os.environ.get("LOCI_AGENT_SECRET", "")
    if not agent_id or len(secret) < 32:
        raise RuntimeError("LOCI_AGENT_ID and a 32-character LOCI_AGENT_SECRET are required")
    projects = _csv("LOCI_PROJECTS")
    operations = _csv("LOCI_OPERATIONS")
    db_path = os.environ.get("LOCI_COORDINATION_DB", ".loci/coordination.sqlite3")
    if db_path != ":memory:":
        Path(db_path).expanduser().parent.mkdir(parents=True, exist_ok=True)
    bus = SecureEventBus(db_path)
    bus.register_agent(agent_id, secret, projects=set(projects), operations=set(operations),
                       reviewer=_truthy("LOCI_REVIEWER"))

    try:
        peers = json.loads(os.environ.get("LOCI_PEERS_JSON", "[]"))
    except json.JSONDecodeError as exc:
        raise RuntimeError("LOCI_PEERS_JSON must be valid JSON") from exc
    if not isinstance(peers, list):
        raise RuntimeError("LOCI_PEERS_JSON must be a JSON array")
    for peer in peers:
        if not isinstance(peer, dict):
            raise RuntimeError("each LOCI peer must be an object")
        try:
            peer_id = str(peer["agent_id"])
            peer_secret = str(peer["secret"])
            peer_projects = set(peer["projects"])
            peer_operations = set(peer["operations"])
        except (KeyError, TypeError) as exc:
            raise RuntimeError("peer requires agent_id, secret, projects, and operations") from exc
        bus.register_agent(peer_id, peer_secret, projects=peer_projects, operations=peer_operations,
                           reviewer=bool(peer.get("reviewer", False)))
    return CoordinationRuntime(agent_id, bus, TaskBoard(bus), projects, operations,
                               _truthy("LOCI_REVIEWER"))


_runtime: CoordinationRuntime | None = None


def _get_runtime() -> CoordinationRuntime:
    global _runtime
    if _runtime is None:
        _runtime = _load_runtime()
    return _runtime


mcp = FastMCP("loci-coordination") if FastMCP is not None else None


def _register(fn: F) -> F:
    if mcp is not None:
        return mcp.tool()(fn)  # type: ignore[no-any-return]
    return fn


def _project_allowed(runtime: CoordinationRuntime, project_id: str) -> None:
    policy: AgentPolicy | None = runtime.bus.policies.get(runtime.agent_id)
    if not policy or project_id not in policy.projects:
        raise AuthorizationError("agent is not authorized for project")


def _task_view(runtime: CoordinationRuntime, task_id: str) -> dict[str, Any]:
    task = runtime.board._task(task_id)
    _project_allowed(runtime, task["project_id"])
    return {
        "task_id": task["task_id"], "project_id": task["project_id"], "title": task["title"],
        "state": task["state"], "owner": task["owner"], "lease_until": task["lease_until"],
        "base_commit": task["base_commit"], "allowed_paths": json.loads(task["allowed_paths"]),
        "review_status": task["review_status"], "tests_passed": bool(task["tests_passed"]),
        "artifact_sha256": task["artifact_sha256"], "updated_at": task["updated_at"],
    }


def _event_view(event: Any) -> dict[str, Any]:
    return {
        "event_id": event.event_id, "correlation_id": event.correlation_id,
        "project_id": event.project_id, "task_id": event.task_id,
        "sender_agent": event.sender_agent, "recipient_agent": event.recipient_agent,
        "event_type": event.event_type, "operation": event.operation,
        "payload": dict(event.payload), "sequence": event.sequence,
        "issued_at": event.issued_at, "expires_at": event.expires_at,
        "base_commit": event.base_commit,
    }


@_register
def coordination_identity() -> dict[str, Any]:
    """Return the bound identity and scope; never return secrets."""
    runtime = _get_runtime()
    return {"agent_id": runtime.agent_id, "projects": sorted(runtime.projects),
            "operations": sorted(runtime.operations), "reviewer": runtime.reviewer}


@_register
def coordination_create_task(project_id: str, title: str, base_commit: str,
                             allowed_paths: list[str]) -> dict[str, Any]:
    """Create a project-scoped task."""
    runtime = _get_runtime()
    task_id = runtime.board.create(agent=runtime.agent_id, project=project_id, title=title,
                                   base_commit=base_commit, allowed_paths=tuple(allowed_paths))
    return _task_view(runtime, task_id)


@_register
def coordination_claim_task(task_id: str, lease_seconds: int = 900) -> dict[str, Any]:
    """Claim a task lease for this agent."""
    runtime = _get_runtime()
    runtime.board.claim(agent=runtime.agent_id, task_id=task_id, lease_seconds=lease_seconds)
    return _task_view(runtime, task_id)


@_register
def coordination_heartbeat(task_id: str, lease_seconds: int = 900) -> dict[str, Any]:
    """Renew the current task lease."""
    runtime = _get_runtime()
    runtime.board.heartbeat(agent=runtime.agent_id, task_id=task_id, lease_seconds=lease_seconds)
    return _task_view(runtime, task_id)


@_register
def coordination_complete_task(task_id: str, commit_sha: str, tests_passed: bool,
                               artifact_sha256: str | None = None) -> dict[str, Any]:
    """Record tested completion; review is still required."""
    runtime = _get_runtime()
    runtime.board.complete(agent=runtime.agent_id, task_id=task_id, commit_sha=commit_sha,
                           tests_passed=tests_passed, artifact_sha256=artifact_sha256)
    return _task_view(runtime, task_id)


@_register
def coordination_request_review(task_id: str) -> dict[str, Any]:
    """Submit a tested task to an authorized reviewer."""
    runtime = _get_runtime()
    runtime.board.request_review(agent=runtime.agent_id, task_id=task_id)
    return _task_view(runtime, task_id)


@_register
def coordination_approve_review(task_id: str) -> dict[str, Any]:
    """Approve a pending task as a configured reviewer."""
    runtime = _get_runtime()
    runtime.board.approve(reviewer=runtime.agent_id, task_id=task_id)
    return _task_view(runtime, task_id)


@_register
def coordination_open_conflict(task_id: str, details: dict[str, Any]) -> dict[str, Any]:
    """Block a task and record a data-only conflict description."""
    runtime = _get_runtime()
    conflict_id = runtime.board.open_conflict(agent=runtime.agent_id, task_id=task_id, details=details)
    return {"conflict_id": conflict_id, "task": _task_view(runtime, task_id)}


@_register
def coordination_send_message(project_id: str, recipient_agent: str, message: str) -> dict[str, Any]:
    """Send a bounded data-only message to a project-scoped peer; never execute it."""
    runtime = _get_runtime()
    if not message.strip():
        raise CoordinationError("message must not be empty")
    event = runtime.bus.publish(sender_agent=runtime.agent_id, project_id=project_id,
                                event_type="agent.message", operation="send_message",
                                recipient_agent=recipient_agent, payload={"message": message})
    return _event_view(event)


@_register
def coordination_list_events(project_id: str, after_sequence: int = 0) -> list[dict[str, Any]]:
    """Replay visible project events after a sequence number."""
    runtime = _get_runtime()
    _project_allowed(runtime, project_id)
    events = runtime.bus.events(project_id, after_sequence)
    return [_event_view(event) for event in events
            if event.recipient_agent is None or event.sender_agent == runtime.agent_id
            or event.recipient_agent == runtime.agent_id]


@_register
def coordination_task_status(task_id: str) -> dict[str, Any]:
    """Read a task in this agent's configured project scope."""
    return _task_view(_get_runtime(), task_id)


def main() -> None:
    if mcp is None:
        raise SystemExit("MCP SDK is not installed; install the coordination extra first")
    _get_runtime()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
