"""Secure local-first inter-agent coordination for LOCI projects."""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Mapping, Protocol

SCHEMA = "loci.task.v1"
MAX_PAYLOAD = 16_384
PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
EVENTS = frozenset({"task.created", "task.claimed", "task.heartbeat", "task.completed",
                    "review.requested", "review.approved", "conflict.opened",
                    "conflict.resolved", "memory.summary", "agent.message"})
OPS = frozenset({"create_task", "claim_task", "heartbeat", "complete_task",
                 "request_review", "approve_review", "open_conflict",
                 "resolve_conflict", "record_memory", "send_message"})
FORBIDDEN = frozenset({"command", "commands", "shell", "exec", "tool_call",
                       "permissions", "credentials", "secret", "token",
                       "api_key", "system_prompt"})


class CoordinationError(Exception):
    pass


class AuthorizationError(CoordinationError):
    pass


class ProtocolError(CoordinationError):
    pass


class ReplayError(ProtocolError):
    pass


class LeaseError(CoordinationError):
    pass


class ReviewGateError(CoordinationError):
    pass


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def _uuid(value: str, name: str) -> None:
    try:
        uuid.UUID(value)
    except (ValueError, TypeError, AttributeError) as exc:
        raise ProtocolError(f"{name} must be a UUID") from exc


def _paths(paths: tuple[str, ...]) -> None:
    for value in paths:
        path = PurePosixPath(value)
        if not value or path.is_absolute() or ".." in path.parts:
            raise ProtocolError("allowed_paths must be relative and cannot contain '..'")


def _payload(payload: Mapping[str, Any]) -> None:
    if not isinstance(payload, Mapping):
        raise ProtocolError("payload must be an object")
    if len(_canonical(payload)) > MAX_PAYLOAD:
        raise ProtocolError("payload is too large")
    forbidden = FORBIDDEN.intersection(payload.keys())
    if forbidden:
        raise ProtocolError("payload contains authority-bearing fields: " + ", ".join(sorted(forbidden)))


@dataclass(frozen=True)
class AgentPolicy:
    projects: frozenset[str]
    operations: frozenset[str]
    reviewer: bool = False

    def allows(self, project: str, operation: str) -> bool:
        return project in self.projects and operation in self.operations


@dataclass(frozen=True)
class EventEnvelope:
    event_id: str
    correlation_id: str
    project_id: str
    sender_agent: str
    event_type: str
    operation: str
    payload: Mapping[str, Any]
    sequence: int
    idempotency_key: str
    issued_at: float
    expires_at: float
    signature: str
    task_id: str | None = None
    recipient_agent: str | None = None
    base_commit: str | None = None
    allowed_paths: tuple[str, ...] = ()
    schema: str = SCHEMA

    def unsigned(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "event_id": self.event_id,
            "correlation_id": self.correlation_id, "project_id": self.project_id,
            "sender_agent": self.sender_agent, "recipient_agent": self.recipient_agent,
            "event_type": self.event_type, "operation": self.operation,
            "base_commit": self.base_commit, "allowed_paths": list(self.allowed_paths),
            "payload": dict(self.payload), "sequence": self.sequence,
            "idempotency_key": self.idempotency_key,
            "issued_at": self.issued_at, "expires_at": self.expires_at,
        }

    def sign(self, secret: str) -> "EventEnvelope":
        signature = hmac.new(secret.encode(), _canonical(self.unsigned()), hashlib.sha256).hexdigest()
        return EventEnvelope(**{**self.__dict__, "signature": signature})

    def validate(self, now: float | None = None) -> None:
        if self.schema != SCHEMA:
            raise ProtocolError("unsupported schema")
        _uuid(self.event_id, "event_id")
        _uuid(self.correlation_id, "correlation_id")
        if self.task_id:
            _uuid(self.task_id, "task_id")
        if not PROJECT_RE.fullmatch(self.project_id):
            raise ProtocolError("invalid project_id")
        if not self.sender_agent.strip() or self.event_type not in EVENTS or self.operation not in OPS:
            raise ProtocolError("invalid sender, event_type, or operation")
        if self.recipient_agent == self.sender_agent:
            raise ProtocolError("sender cannot be its own recipient")
        if self.base_commit is not None and not SHA_RE.fullmatch(self.base_commit):
            raise ProtocolError("base_commit must be a full hexadecimal Git SHA")
        _paths(self.allowed_paths)
        _payload(self.payload)
        if self.sequence < 1 or not self.idempotency_key or len(self.idempotency_key) > 200:
            raise ProtocolError("invalid sequence or idempotency_key")
        if not re.fullmatch(r"[0-9a-f]{64}", self.signature):
            raise ProtocolError("invalid signature")
        if self.expires_at <= self.issued_at or self.expires_at - self.issued_at > 86_400:
            raise ProtocolError("invalid event lifetime")
        if (time.time() if now is None else now) > self.expires_at:
            raise ProtocolError("event has expired")


class MemorySink(Protocol):
    def record_event(self, event: EventEnvelope) -> None: ...


class SecureEventBus:
    def __init__(self, db_path: str = ":memory:", *, memory_sink: MemorySink | None = None):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA busy_timeout=5000")
        if db_path != ":memory:":
            self.db.execute("PRAGMA journal_mode=WAL")
        self.secrets: dict[str, str] = {}
        self.policies: dict[str, AgentPolicy] = {}
        self.memory_sink = memory_sink
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, schema TEXT NOT NULL, correlation_id TEXT NOT NULL,
                project_id TEXT NOT NULL, task_id TEXT, sender_agent TEXT NOT NULL,
                recipient_agent TEXT, event_type TEXT NOT NULL, operation TEXT NOT NULL,
                base_commit TEXT, allowed_paths TEXT NOT NULL, payload TEXT NOT NULL,
                issued_at REAL NOT NULL, expires_at REAL NOT NULL, sequence INTEGER NOT NULL,
                idempotency_key TEXT NOT NULL UNIQUE, signature TEXT NOT NULL,
                UNIQUE(project_id, sender_agent, sequence)
            );
            CREATE INDEX IF NOT EXISTS events_project_sequence ON events(project_id, sequence);
        """)

    def close(self) -> None:
        self.db.close()

    def register_agent(self, agent_id: str, secret: str, *, projects: set[str],
                       operations: set[str], reviewer: bool = False) -> None:
        if not agent_id.strip() or len(secret) < 32:
            raise AuthorizationError("agent ID and a 32-character secret are required")
        if not projects or any(not PROJECT_RE.fullmatch(p) for p in projects):
            raise AuthorizationError("invalid project scope")
        if not operations or not operations.issubset(OPS):
            raise AuthorizationError("invalid operation scope")
        self.secrets[agent_id] = secret
        self.policies[agent_id] = AgentPolicy(frozenset(projects), frozenset(operations), reviewer)

    @staticmethod
    def new_secret() -> str:
        return secrets.token_urlsafe(32)

    def authorize(self, agent: str, project: str, operation: str) -> None:
        policy = self.policies.get(agent)
        if policy is None or not policy.allows(project, operation):
            raise AuthorizationError("agent is not authorized for project/operation")

    def publish(self, *, sender_agent: str, project_id: str, event_type: str,
                operation: str, payload: Mapping[str, Any], task_id: str | None = None,
                recipient_agent: str | None = None, base_commit: str | None = None,
                allowed_paths: tuple[str, ...] = (), expires_in: int = 900) -> EventEnvelope:
        self.authorize(sender_agent, project_id, operation)
        if not 1 <= expires_in <= 86_400:
            raise ProtocolError("expires_in out of range")
        latest = self.db.execute(
            "SELECT COALESCE(MAX(sequence),0) FROM events WHERE project_id=? AND sender_agent=?",
            (project_id, sender_agent)).fetchone()[0]
        now = time.time()
        event = EventEnvelope(
            event_id=str(uuid.uuid4()), correlation_id=str(uuid.uuid4()),
            project_id=project_id, sender_agent=sender_agent, event_type=event_type,
            operation=operation, payload=payload, sequence=int(latest) + 1,
            idempotency_key=f"{sender_agent}:{uuid.uuid4()}", issued_at=now,
            expires_at=now + expires_in, task_id=task_id, recipient_agent=recipient_agent,
            base_commit=base_commit, allowed_paths=allowed_paths, signature="0" * 64,
        ).sign(self.secrets[sender_agent])
        self.accept(event)
        return event

    def accept(self, event: EventEnvelope) -> bool:
        event.validate()
        secret = self.secrets.get(event.sender_agent)
        if secret is None or not hmac.compare_digest(
                event.signature,
                hmac.new(secret.encode(), _canonical(event.unsigned()), hashlib.sha256).hexdigest()):
            raise AuthorizationError("signature verification failed")
        self.authorize(event.sender_agent, event.project_id, event.operation)
        if event.recipient_agent:
            recipient_policy = self.policies.get(event.recipient_agent)
            if not recipient_policy or event.project_id not in recipient_policy.projects:
                raise AuthorizationError("recipient is not authorized for this project")
        existing = self.db.execute(
            "SELECT signature FROM events WHERE idempotency_key=?", (event.idempotency_key,)).fetchone()
        if existing:
            if existing[0] != event.signature:
                raise ReplayError("idempotency key was reused with different content")
            return False
        latest = self.db.execute(
            "SELECT COALESCE(MAX(sequence),0) FROM events WHERE project_id=? AND sender_agent=?",
            (event.project_id, event.sender_agent)).fetchone()[0]
        if event.sequence != int(latest) + 1:
            raise ReplayError("sequence gap or replay")
        self.db.execute(
            "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (event.event_id, event.schema, event.correlation_id, event.project_id, event.task_id,
             event.sender_agent, event.recipient_agent, event.event_type, event.operation,
             event.base_commit, json.dumps(list(event.allowed_paths)),
             json.dumps(dict(event.payload), sort_keys=True), event.issued_at, event.expires_at,
             event.sequence, event.idempotency_key, event.signature))
        self.db.commit()
        if self.memory_sink and event.event_type in {"task.completed", "review.approved",
                                                       "conflict.resolved", "memory.summary"}:
            self.memory_sink.record_event(event)
        return True

    def events(self, project_id: str, after_sequence: int = 0) -> list[EventEnvelope]:
        rows = self.db.execute(
            "SELECT * FROM events WHERE project_id=? AND sequence>? ORDER BY sequence",
            (project_id, after_sequence)).fetchall()
        return [EventEnvelope(
            event_id=row["event_id"], schema=row["schema"], correlation_id=row["correlation_id"],
            project_id=row["project_id"], task_id=row["task_id"], sender_agent=row["sender_agent"],
            recipient_agent=row["recipient_agent"], event_type=row["event_type"],
            operation=row["operation"], base_commit=row["base_commit"],
            allowed_paths=tuple(json.loads(row["allowed_paths"])),
            payload=json.loads(row["payload"]), issued_at=row["issued_at"],
            expires_at=row["expires_at"], sequence=row["sequence"],
            idempotency_key=row["idempotency_key"], signature=row["signature"])
            for row in rows]

    def verified_events(self, project_id: str, *, recipient_agent: str | None = None,
                        after_rowid: int = 0) -> list[tuple[int, EventEnvelope]]:
        """Read events back with the same schema/HMAC verification `accept()` applies at write
        time. `events()` alone does NOT re-verify signatures on read — a row inserted by any
        means other than `accept()` (a direct DB write, a restored backup, a bug) would be
        returned by `events()` unchecked. Callers that will act on payload content should use
        this method, not `events()`.

        Ordered by SQLite `rowid` (global and monotonically increasing within this database),
        not `sequence` — `sequence` is scoped per `(project_id, sender_agent)`
        (see the `UNIQUE(project_id, sender_agent, sequence)` constraint above), so two
        different senders' events can legitimately carry the same sequence number. Per-sender
        sequence gaps/replays are already rejected by `accept()` at write time; this method adds
        the read-time signature check `events()` is missing, using `rowid` as a safe delivery
        cursor since it cannot collide across senders.

        A row that fails validation or signature verification is silently excluded, not raised —
        a single tampered/undecodable row should not block delivery of every event after it.
        """
        query = "SELECT rowid, * FROM events WHERE project_id=? AND rowid>?"
        params: list[Any] = [project_id, after_rowid]
        if recipient_agent is not None:
            query += " AND recipient_agent=?"
            params.append(recipient_agent)
        query += " ORDER BY rowid"
        rows = self.db.execute(query, params).fetchall()
        verified: list[tuple[int, EventEnvelope]] = []
        for row in rows:
            event = EventEnvelope(
                event_id=row["event_id"], schema=row["schema"], correlation_id=row["correlation_id"],
                project_id=row["project_id"], task_id=row["task_id"], sender_agent=row["sender_agent"],
                recipient_agent=row["recipient_agent"], event_type=row["event_type"],
                operation=row["operation"], base_commit=row["base_commit"],
                allowed_paths=tuple(json.loads(row["allowed_paths"])),
                payload=json.loads(row["payload"]), issued_at=row["issued_at"],
                expires_at=row["expires_at"], sequence=row["sequence"],
                idempotency_key=row["idempotency_key"], signature=row["signature"])
            try:
                event.validate(now=event.issued_at)
            except ProtocolError:
                continue
            secret = self.secrets.get(event.sender_agent)
            if secret is None:
                continue
            expected = hmac.new(secret.encode(), _canonical(event.unsigned()), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(event.signature, expected):
                continue
            verified.append((row["rowid"], event))
        return verified


class TaskBoard:
    def __init__(self, bus: SecureEventBus):
        self.bus = bus
        self.db = bus.db
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, title TEXT NOT NULL,
                state TEXT NOT NULL, owner TEXT, lease_until REAL, base_commit TEXT NOT NULL,
                allowed_paths TEXT NOT NULL, review_status TEXT NOT NULL DEFAULT 'none',
                tests_passed INTEGER NOT NULL DEFAULT 0, artifact_sha256 TEXT,
                updated_at REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS conflicts (
                conflict_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, project_id TEXT NOT NULL,
                state TEXT NOT NULL, details TEXT NOT NULL, resolution TEXT, updated_at REAL NOT NULL
            );
        """)

    def create(self, *, agent: str, project: str, title: str, base_commit: str,
               allowed_paths: tuple[str, ...], task_id: str | None = None) -> str:
        self.bus.authorize(agent, project, "create_task")
        if not title.strip() or not SHA_RE.fullmatch(base_commit):
            raise ProtocolError("invalid task title or base commit")
        _paths(allowed_paths)
        task_id = task_id or str(uuid.uuid4())
        _uuid(task_id, "task_id")
        self.db.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, 'ready', NULL, NULL, ?, ?, 'none', 0, NULL, ?)",
            (task_id, project, title, base_commit, json.dumps(list(allowed_paths)), time.time()))
        self.db.commit()
        self.bus.publish(sender_agent=agent, project_id=project, event_type="task.created",
                         operation="create_task", task_id=task_id, base_commit=base_commit,
                         allowed_paths=allowed_paths, payload={"title": title})
        return task_id

    def _task(self, task_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if not row:
            raise CoordinationError("task not found")
        return row

    def claim(self, *, agent: str, task_id: str, lease_seconds: int = 900) -> None:
        task = self._task(task_id)
        self.bus.authorize(agent, task["project_id"], "claim_task")
        now = time.time()
        if task["state"] not in {"ready", "claimed", "blocked"}:
            raise LeaseError("task is not claimable")
        if task["owner"] not in (None, agent) and (task["lease_until"] or 0) > now:
            raise LeaseError("task is leased by another agent")
        if not 1 <= lease_seconds <= 86_400:
            raise ProtocolError("lease out of range")
        until = now + lease_seconds
        self.db.execute("UPDATE tasks SET state='claimed', owner=?, lease_until=?, updated_at=? WHERE task_id=?",
                        (agent, until, now, task_id))
        self.db.commit()
        self.bus.publish(sender_agent=agent, project_id=task["project_id"],
                         event_type="task.claimed", operation="claim_task", task_id=task_id,
                         base_commit=task["base_commit"],
                         allowed_paths=tuple(json.loads(task["allowed_paths"])),
                         payload={"lease_until": until})

    def heartbeat(self, *, agent: str, task_id: str, lease_seconds: int = 900) -> None:
        task = self._owned(agent, task_id, "heartbeat")
        if not 1 <= lease_seconds <= 86_400:
            raise ProtocolError("lease out of range")
        until = time.time() + lease_seconds
        self.db.execute("UPDATE tasks SET lease_until=?, updated_at=? WHERE task_id=?",
                        (until, time.time(), task_id))
        self.db.commit()
        self.bus.publish(sender_agent=agent, project_id=task["project_id"],
                         event_type="task.heartbeat", operation="heartbeat", task_id=task_id,
                         base_commit=task["base_commit"],
                         allowed_paths=tuple(json.loads(task["allowed_paths"])),
                         expires_in=lease_seconds, payload={"lease_until": until})

    def complete(self, *, agent: str, task_id: str, commit_sha: str,
                 tests_passed: bool, artifact_sha256: str | None = None) -> None:
        task = self._owned(agent, task_id, "complete_task")
        if not tests_passed or not SHA_RE.fullmatch(commit_sha):
            raise ReviewGateError("completion requires passing tests and a full commit SHA")
        if artifact_sha256 and not re.fullmatch(r"[0-9a-f]{64}", artifact_sha256):
            raise ProtocolError("invalid artifact checksum")
        self.db.execute("UPDATE tasks SET state='completed', lease_until=NULL, tests_passed=1, artifact_sha256=?, updated_at=? WHERE task_id=?",
                        (artifact_sha256, time.time(), task_id))
        self.db.commit()
        self.bus.publish(sender_agent=agent, project_id=task["project_id"],
                         event_type="task.completed", operation="complete_task", task_id=task_id,
                         base_commit=commit_sha, payload={"tests_passed": True, "artifact_sha256": artifact_sha256})

    def request_review(self, *, agent: str, task_id: str) -> None:
        task = self._task(task_id)
        self.bus.authorize(agent, task["project_id"], "request_review")
        if task["owner"] != agent:
            raise LeaseError("task owner required")
        if task["state"] != "completed" or not task["tests_passed"]:
            raise ReviewGateError("only tested tasks can enter review")
        self.db.execute("UPDATE tasks SET state='review', review_status='pending', updated_at=? WHERE task_id=?",
                        (time.time(), task_id))
        self.db.commit()
        self.bus.publish(sender_agent=agent, project_id=task["project_id"],
                         event_type="review.requested", operation="request_review", task_id=task_id,
                         base_commit=task["base_commit"], payload={})

    def approve(self, *, reviewer: str, task_id: str) -> None:
        task = self._task(task_id)
        policy = self.bus.policies.get(reviewer)
        if not policy or not policy.reviewer:
            raise AuthorizationError("agent is not a reviewer")
        self.bus.authorize(reviewer, task["project_id"], "approve_review")
        if task["state"] != "review" or task["review_status"] != "pending":
            raise ReviewGateError("task is not awaiting review")
        self.db.execute("UPDATE tasks SET state='approved', review_status='approved', updated_at=? WHERE task_id=?",
                        (time.time(), task_id))
        self.db.commit()
        self.bus.publish(sender_agent=reviewer, project_id=task["project_id"],
                         event_type="review.approved", operation="approve_review", task_id=task_id,
                         base_commit=task["base_commit"], payload={})

    def open_conflict(self, *, agent: str, task_id: str, details: Mapping[str, Any]) -> str:
        task = self._owned(agent, task_id, "open_conflict")
        _payload(details)
        conflict_id = str(uuid.uuid4())
        self.db.execute("INSERT INTO conflicts VALUES (?, ?, ?, 'open', ?, NULL, ?)",
                        (conflict_id, task_id, task["project_id"], json.dumps(dict(details)), time.time()))
        self.db.execute("UPDATE tasks SET state='blocked', updated_at=? WHERE task_id=?",
                        (time.time(), task_id))
        self.db.commit()
        self.bus.publish(sender_agent=agent, project_id=task["project_id"],
                         event_type="conflict.opened", operation="open_conflict", task_id=task_id,
                         base_commit=task["base_commit"], payload={"conflict_id": conflict_id, "details": dict(details)})
        return conflict_id

    def _owned(self, agent: str, task_id: str, operation: str) -> sqlite3.Row:
        task = self._task(task_id)
        self.bus.authorize(agent, task["project_id"], operation)
        if task["owner"] != agent or (task["lease_until"] or 0) <= time.time():
            raise LeaseError("agent does not hold a live task lease")
        return task



