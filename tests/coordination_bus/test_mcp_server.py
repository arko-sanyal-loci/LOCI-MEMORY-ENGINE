import pytest

from coordination_bus import mcp_server as coordination_mcp
from coordination_bus.bus import AuthorizationError, EventEnvelope, ReplayError, SecureEventBus, TaskBoard
from coordination_bus.mcp_server import CoordinationRuntime

SHA = "a" * 40
CLAUDE_SECRET = "c" * 32
CODEX_SECRET = "d" * 32
PORTFOLIO_SECRET = "p" * 32
REVIEWER_SECRET = "r" * 32


def _runtime(bus, agent_id, operations, reviewer=False):
    return CoordinationRuntime(
        agent_id=agent_id,
        bus=bus,
        board=TaskBoard(bus),
        projects=frozenset({"codex-rag"}),
        operations=frozenset(operations),
        reviewer=reviewer,
    )


@pytest.fixture
def shared_runtime(tmp_path, monkeypatch):
    db = tmp_path / "coordination.sqlite3"
    bus = SecureEventBus(str(db))
    bus.register_agent("claude-code", CLAUDE_SECRET, projects={"codex-rag"},
                       operations={"send_message"})
    bus.register_agent("codex", CODEX_SECRET, projects={"codex-rag"},
                       operations={"send_message", "claim_task", "complete_task",
                                   "request_review"})
    bus.register_agent("portfolio", PORTFOLIO_SECRET, projects={"codex-rag"},
                       operations={"create_task"})
    bus.register_agent("reviewer", REVIEWER_SECRET, projects={"codex-rag"},
                       operations={"approve_review"}, reviewer=True)
    runtime = _runtime(bus, "claude-code", {"send_message"})
    monkeypatch.setattr(coordination_mcp, "_runtime", runtime)
    yield bus
    bus.close()


def test_cross_agent_message_is_scoped_and_integrity_checked(shared_runtime, monkeypatch):
    event = coordination_mcp.coordination_send_message(
        "codex-rag", "codex", "The bounded test completed."
    )
    assert event["event_type"] == "agent.message"
    assert event["recipient_agent"] == "codex"

    monkeypatch.setattr(
        coordination_mcp, "_runtime", _runtime(shared_runtime, "codex", {"send_message"})
    )
    visible = coordination_mcp.coordination_list_events("codex-rag")
    assert any(item["event_id"] == event["event_id"] for item in visible)

    original = shared_runtime.events("codex-rag")[0]
    tampered = EventEnvelope(**{**original.__dict__, "payload": {"message": "forged"}}).sign(
        CLAUDE_SECRET
    )
    with pytest.raises((AuthorizationError, ReplayError)):
        shared_runtime.accept(tampered)

    monkeypatch.setattr(
        coordination_mcp, "_runtime", _runtime(shared_runtime, "claude-code", {"send_message"})
    )
    with pytest.raises(AuthorizationError):
        coordination_mcp.coordination_list_events("other-project")


def test_mcp_task_flow_requires_review(shared_runtime, monkeypatch):
    monkeypatch.setattr(
        coordination_mcp, "_runtime", _runtime(shared_runtime, "portfolio", {"create_task"})
    )
    task = coordination_mcp.coordination_create_task(
        "codex-rag", "MCP adapter", SHA, ["rag/", "tests/"]
    )
    assert task["state"] == "ready"

    monkeypatch.setattr(
        coordination_mcp, "_runtime",
        _runtime(shared_runtime, "codex", {
            "claim_task", "complete_task", "request_review", "send_message"
        }),
    )
    assert coordination_mcp.coordination_claim_task(task["task_id"])["state"] == "claimed"
    completed = coordination_mcp.coordination_complete_task(
        task["task_id"], SHA, True
    )
    assert completed["state"] == "completed"
    pending = coordination_mcp.coordination_request_review(task["task_id"])
    assert pending["review_status"] == "pending"

    monkeypatch.setattr(
        coordination_mcp, "_runtime",
        _runtime(shared_runtime, "reviewer", {"approve_review"}, reviewer=True),
    )
    approved = coordination_mcp.coordination_approve_review(task["task_id"])
    assert approved["state"] == "approved"

def test_mcp_tool_discovery():
    import asyncio

    assert coordination_mcp.mcp is not None
    tools = asyncio.run(coordination_mcp.mcp.list_tools())
    names = {tool.name for tool in tools}
    assert {
        "coordination_identity",
        "coordination_send_message",
        "coordination_claim_task",
        "coordination_complete_task",
        "coordination_request_review",
        "coordination_approve_review",
        "coordination_list_events",
    }.issubset(names)