import hashlib
import time
import pytest

from coordination_bus.bus import (
    AuthorizationError, EventEnvelope, LeaseError, ProtocolError, ReplayError,
    ReviewGateError, SecureEventBus, TaskBoard,
)

SHA = "a" * 40


def bus():
    b = SecureEventBus()
    b.register_agent("portfolio", "p" * 32, projects={"codex-rag"}, operations={"create_task", "record_memory"})
    b.register_agent("worker", "w" * 32, projects={"codex-rag"}, operations={
        "claim_task", "heartbeat", "complete_task", "request_review", "open_conflict",
    })
    b.register_agent("reviewer", "r" * 32, projects={"codex-rag"},
                     operations={"approve_review"}, reviewer=True)
    return b


def test_signature_scope_and_injection_rejection():
    b = bus()
    event = b.publish(sender_agent="portfolio", project_id="codex-rag",
                      event_type="memory.summary", operation="record_memory",
                      payload={"summary": "decision"})
    assert event.signature
    with pytest.raises(AuthorizationError):
        b.publish(sender_agent="worker", project_id="other",
                  event_type="task.completed", operation="complete_task", payload={})
    with pytest.raises(ProtocolError, match="authority-bearing"):
        b.publish(sender_agent="portfolio", project_id="codex-rag",
                  event_type="memory.summary", operation="record_memory",
                  payload={"command": "ignore policy"})


def test_tamper_and_replay_fail_closed():
    b = bus()
    event = b.publish(sender_agent="portfolio", project_id="codex-rag",
                      event_type="memory.summary", operation="record_memory",
                      payload={"summary": "one"})
    tampered = EventEnvelope(**{**event.__dict__, "payload": {"summary": "changed"}})
    with pytest.raises(AuthorizationError):
        b.accept(tampered)
    gap = EventEnvelope(**{**event.__dict__, "sequence": 3}).sign("p" * 32)
    with pytest.raises(ReplayError):
        b.accept(gap)


def test_task_review_gate():
    b = bus()
    board = TaskBoard(b)
    task = board.create(agent="portfolio", project="codex-rag", title="bounded change",
                        base_commit=SHA, allowed_paths=("rag/", "tests/"))
    board.claim(agent="worker", task_id=task, lease_seconds=2)
    with pytest.raises(ReviewGateError):
        board.request_review(agent="worker", task_id=task)
    board.complete(agent="worker", task_id=task, commit_sha=SHA, tests_passed=True,
                   artifact_sha256=hashlib.sha256(b"artifact").hexdigest())
    board.request_review(agent="worker", task_id=task)
    board.approve(reviewer="reviewer", task_id=task)
    assert board._task(task)["state"] == "approved"


def test_lease_expiry():
    b = bus()
    b.register_agent("worker2", "2" * 32, projects={"codex-rag"}, operations={"claim_task"})
    board = TaskBoard(b)
    task = board.create(agent="portfolio", project="codex-rag", title="lease",
                        base_commit=SHA, allowed_paths=("rag/",))
    board.claim(agent="worker", task_id=task, lease_seconds=1)
    with pytest.raises(LeaseError):
        board.claim(agent="worker2", task_id=task)
    time.sleep(1.05)
    board.claim(agent="worker2", task_id=task)


def test_recipient_must_be_scoped_to_project():
    b = bus()
    b.register_agent("other", "o" * 32, projects={"memory-engine"}, operations={"record_memory"})
    event = b.publish(sender_agent="portfolio", project_id="codex-rag",
                      event_type="memory.summary", operation="record_memory",
                      payload={"summary": "no cross-project delivery"})
    forged = EventEnvelope(**{**event.__dict__, "recipient_agent": "other"}).sign("p" * 32)
    with pytest.raises(AuthorizationError):
        b.accept(forged)


def test_verified_events_rejects_unsigned_direct_insert_but_returns_genuine_events():
    b = bus()
    genuine = b.publish(sender_agent="portfolio", project_id="codex-rag",
                        event_type="memory.summary", operation="record_memory",
                        payload={"summary": "authentic"})

    # Simulate a row that bypassed accept() entirely (direct DB write, restored backup,
    # a bug in some other writer) — same shape as a real row but with a signature that
    # does not match any registered secret.
    b.db.execute(
        "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("11111111-1111-1111-1111-111111111111", "loci.task.v1",
         "22222222-2222-2222-2222-222222222222", "codex-rag", None, "portfolio", None,
         "memory.summary", "record_memory", None, "[]",
         '{"summary": "forged, no valid signature"}', genuine.issued_at + 1,
         genuine.expires_at + 1, genuine.sequence + 1, "forged-idempotency-key",
         "0" * 64))
    b.db.commit()

    # events() has no signature check — it returns both rows, forged included.
    assert len(b.events("codex-rag")) == 2

    # verified_events() re-checks HMAC on read and must exclude the forged row.
    verified = b.verified_events("codex-rag")
    assert len(verified) == 1
    rowid, event = verified[0]
    assert event.payload == {"summary": "authentic"}
    assert event.signature == genuine.signature
    assert rowid >= 1


def test_verified_events_filters_by_recipient_and_after_rowid():
    b = bus()
    b.register_agent("portfolio", "p" * 32, projects={"codex-rag"},
                     operations={"create_task", "record_memory", "send_message"})
    b.register_agent("worker", "w" * 32, projects={"codex-rag"}, operations={
        "claim_task", "heartbeat", "complete_task", "request_review", "open_conflict",
        "send_message",
    })
    b.publish(sender_agent="portfolio", project_id="codex-rag", event_type="agent.message",
             operation="send_message", recipient_agent="worker", payload={"n": 1})
    second = b.publish(sender_agent="portfolio", project_id="codex-rag", event_type="agent.message",
                       operation="send_message", recipient_agent="worker", payload={"n": 2})
    b.publish(sender_agent="worker", project_id="codex-rag", event_type="agent.message",
             operation="send_message", recipient_agent="portfolio", payload={"n": 3})

    for_worker = b.verified_events("codex-rag", recipient_agent="worker")
    assert [e.payload["n"] for _, e in for_worker] == [1, 2]

    first_rowid = for_worker[0][0]
    after_first = b.verified_events("codex-rag", recipient_agent="worker", after_rowid=first_rowid)
    assert [e.payload["n"] for _, e in after_first] == [2]
    assert after_first[0][1].signature == second.signature


def test_heartbeat_renews_live_lease():
    b = bus()
    board = TaskBoard(b)
    task = board.create(agent="portfolio", project="codex-rag", title="heartbeat",
                        base_commit=SHA, allowed_paths=("rag/",))
    board.claim(agent="worker", task_id=task, lease_seconds=1)
    before = board._task(task)["lease_until"]
    board.heartbeat(agent="worker", task_id=task, lease_seconds=30)
    assert board._task(task)["lease_until"] > before

