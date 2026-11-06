#!/usr/bin/env python3
"""Default-on memory load for a conversation host that calls this module.

What was already true: LearningStore writes SQLite. A later process that
opens the same file can read those rows. Nothing here previously ran at
the start of a conversation.

What this module adds: conversation_start / process_turn / conversation_end.
A host that imports and calls conversation_start will load that owner's
current lessons. This repository does not install a service, does not edit
Grok Bot, and does not see hidden bot prompts or voice settings.

branch default on; Grok Bot host integration unverified/not activated.

Calling the CLI by hand is not the same as every future chat using it.
"""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from loci_engine.application_policy import assess_application
from loci_engine.learning_store import LearningStore
from loci_engine.symprev_review import review_context

HOST_STATUS = {
    "branch_default_on": True,
    "activates_only_when_called": True,
    "grok_bot_host_integration": "unverified_not_activated",
    "label": "engine default on; actual Grok Bot auto-integration not activated/unverified",
    "manual_cli_is_full_turn_memory": False,
    "all_future_calls_use_this": False,
    "embeddings": "not_used",
}

_OWNER_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STOP = {
    "the", "and", "for", "with", "that", "this", "from", "what", "when",
    "where", "which", "have", "has", "was", "were", "are", "you", "your",
}


@dataclass(frozen=True)
class MemoryConfig:
    autoload: bool
    store_dir: str
    source: str


def resolve_config(environ: Optional[Dict[str, str]] = None, store_dir: Optional[str] = None) -> MemoryConfig:
    """Default is on. The directory is outside the git repo unless overridden.

    LOCI_MEMORY_AUTOLOAD=0 skips loading and does not delete the files.
    LOCI_MEMORY_STORE_DIR chooses the directory. The default is
    ~/.local/share/loci-memory-engine, created only when a call uses it.
    """
    env = os.environ if environ is None else environ
    flag = env.get("LOCI_MEMORY_AUTOLOAD", "1").strip().lower()
    autoload = flag not in {"0", "false", "off", "no"}
    directory = store_dir or env.get("LOCI_MEMORY_STORE_DIR") or str(
        Path.home() / ".local" / "share" / "loci-memory-engine"
    )
    return MemoryConfig(autoload=autoload, store_dir=directory, source="LOCI_MEMORY_AUTOLOAD")


def _owner_file(config: MemoryConfig, owner_id: str) -> Path:
    if not _OWNER_RE.fullmatch(owner_id):
        raise ValueError("owner_id must be 1-64 characters of letters, digits, dot, underscore, or hyphen")
    return Path(config.store_dir) / f"{owner_id}.db"


def _tokens(text: str) -> set:
    return {tok for tok in _TOKEN_RE.findall(text.lower()) if tok not in _STOP and len(tok) > 2}


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stamp(payload: Dict[str, Any], config: MemoryConfig, owner_id: str) -> Dict[str, Any]:
    stamped = dict(payload)
    stamped["wall_time"] = datetime.now(timezone.utc).isoformat()
    stamped["timezone"] = "UTC"
    stamped["monotonic_seconds"] = time.perf_counter()
    stamped["wall_clock_backdated"] = False
    stamped["host_status"] = HOST_STATUS
    try:
        if _OWNER_RE.fullmatch(owner_id):
            path = Path(config.store_dir)
            path.mkdir(parents=True, exist_ok=True)
            with (path / f"{owner_id}.lifecycle.jsonl").open("a", encoding="utf-8") as handle:
                import json
                handle.write(json.dumps(stamped, default=str) + "\n")
    except OSError as exc:
        stamped["lifecycle_log_error"] = f"{type(exc).__name__}: {exc}"
    return stamped


def _open_store(path: Path) -> LearningStore:
    if path.exists() and path.is_file():
        head = path.read_bytes()[:16]
        if head and not head.startswith(b"SQLite format 3"):
            raise sqlite3.DatabaseError("file is not a database")
    path.parent.mkdir(parents=True, exist_ok=True)
    return LearningStore(str(path))


def confirm_fact(
    config: MemoryConfig,
    *,
    owner_id: str,
    task_key: str,
    option_key: str,
    polarity: str,
    outcome_id: str,
    statement: str,
    quantity: float,
    unit: str = "loss",
    now_day: float = 0.0,
    expires_on_day: Optional[float] = None,
) -> Dict[str, Any]:
    """Write one external outcome. Raw chat text is not accepted here."""
    store = _open_store(_owner_file(config, owner_id))
    row = store.record_observed(
        task_key=task_key,
        option_key=option_key,
        polarity=polarity,
        outcome_id=outcome_id,
        statement=statement,
        now_day=now_day,
        expires_on_day=expires_on_day,
        quantity=quantity,
        unit=unit,
    )
    return {
        "id": row["id"],
        "content_sha256": _sha(row["statement"]),
        "source_event_ids": row["source_event_ids"],
        "updated_at": row["updated_at"],
    }


def index_sources(
    config: MemoryConfig,
    *,
    owner_id: str,
    documents: Optional[List[Dict[str, str]]],
    conversation_id: str,
) -> Dict[str, Any]:
    """Index caller-supplied source text. None means the step was skipped.

    A skipped step is not an index. Indexed text is marked as source material,
    not as a confirmed user fact. Wall time is the real time of this call.
    """
    wall_start = datetime.now(timezone.utc)
    mono = time.perf_counter()
    if documents is None:
        return _stamp({
            "engine": "loci_engine.memory_lifecycle",
            "event": "paper_indexing",
            "status": "skipped",
            "actual_index": False,
            "indexed": 0,
            "conversation_id": conversation_id,
            "wall_start": wall_start.isoformat(),
            "monotonic_duration_seconds": 0.0,
        }, config, owner_id)
    try:
        store = _open_store(_owner_file(config, owner_id))
        ids = []
        for doc in documents:
            body = str(doc.get("text") or "")
            label = str(doc.get("id") or "source")
            ids.append(store.note(
                "summary",
                f"[indexed_source not_a_confirmed_user_fact id={label}]\n{body}",
            ))
    except (sqlite3.DatabaseError, OSError, ValueError) as exc:
        return _stamp({
            "engine": "loci_engine.memory_lifecycle",
            "event": "paper_indexing",
            "status": "unavailable",
            "actual_index": False,
            "indexed": 0,
            "reason": f"{type(exc).__name__}: {exc}",
            "conversation_id": conversation_id,
            "wall_start": wall_start.isoformat(),
            "monotonic_duration_seconds": time.perf_counter() - mono,
        }, config, owner_id)
    return _stamp({
        "engine": "loci_engine.memory_lifecycle",
        "event": "paper_indexing",
        "status": "completed",
        "actual_index": True,
        "indexed": len(ids),
        "ids": ids,
        "conversation_id": conversation_id,
        "wall_start": wall_start.isoformat(),
        "wall_end": datetime.now(timezone.utc).isoformat(),
        "monotonic_duration_seconds": time.perf_counter() - mono,
    }, config, owner_id)


def conversation_start(
    config: MemoryConfig,
    *,
    owner_id: str,
    conversation_id: str,
    opening: Optional[str] = None,
    now_day: float = 0.0,
    time_control: Optional[str] = None,
    documents: Optional[List[Dict[str, str]]] = None,
    run_index: bool = False,
) -> Dict[str, Any]:
    """Load this owner's current lessons for a new conversation id.

    An opening selects lessons that share its words. With no opening, active
    goals and current crystallized lessons are eligible, then CARD/Symprev
    bound the packet. Unrelated lessons are not added just to show memory.
    Simulated candidates are not loaded. now_day is a logical clock for
    tests; wall_time is the real UTC time of this call.
    """
    base = {
        "engine": "loci_engine.memory_lifecycle",
        "owner_id": owner_id,
        "conversation_id": conversation_id,
        "logical_day": now_day,
        "time_control": time_control,
        "memories": [],
        "invented": False,
    }
    if run_index:
        index_result = index_sources(
            config, owner_id=owner_id, documents=documents, conversation_id=conversation_id,
        )
    else:
        index_result = {
            "event": "paper_indexing",
            "status": "skipped",
            "actual_index": False,
            "indexed": 0,
            "monotonic_duration_seconds": 0.0,
        }
    base["paper_indexing"] = index_result
    if not config.autoload:
        return _stamp({
            **base,
            "status": "skipped",
            "reason": "LOCI_MEMORY_AUTOLOAD is off; existing files were not deleted",
        }, config, owner_id)

    try:
        path = _owner_file(config, owner_id)
    except ValueError as exc:
        return _stamp({**base, "status": "rejected", "reason": str(exc)}, config, "invalid-owner")

    try:
        store = _open_store(path)
        crystallized = store.list_crystallized(now_day)
        goals = store.list_goals()
    except (sqlite3.DatabaseError, OSError) as exc:
        return _stamp({
            **base,
            "status": "unavailable",
            "reason": f"{type(exc).__name__}: {exc}",
            "store_path": str(path),
        }, config, owner_id)

    policy = assess_application(
        action_name="local_context_inject",
        knowledge=opening or "load owner memory",
        application_point="education_comprehension",
        intent=0.2,
        consent=True,
    )
    opening_rejected = bool(policy.get("injection_blocked"))
    usable_opening = None if opening_rejected else opening

    if usable_opening:
        wanted = _tokens(usable_opening)
        chosen = []
        for row in crystallized:
            blob = _tokens(f"{row['statement']} {row['task_key']} {row['option_key']}")
            if wanted & blob:
                chosen.append(row)
        goal_items = []
    else:
        chosen = list(crystallized)
        goal_items = goals

    items = []
    for row in chosen:
        items.append({
            "id": row["id"],
            "statement": row["statement"],
            "heat": row["heat"],
            "support": True,
            "source_id": row["id"],
        })
    for goal in goal_items:
        items.append({
            "id": goal["id"],
            "statement": goal["statement"],
            "heat": goal["heat"] or 0.5,
            "support": True,
            "source_id": goal["id"],
        })
    exact = []
    by_id = {row["id"]: row for row in chosen}
    for row in chosen:
        evidence = row.get("evidence") or {}
        if evidence.get("quantity") is None:
            continue
        exact.append({
            "id": row["id"],
            "key": row["option_key"],
            "quantity": evidence["quantity"],
            "unit": evidence.get("unit"),
            "polarity": row["polarity"],
            "source_id": row["id"],
            "supersedes": row.get("supersedes_id"),
            "valid_from": evidence.get("valid_from"),
            "valid_until": row.get("expires_on_day"),
        })
    query = usable_opening or "active goals verified long lived facts"
    packet = review_context(
        query=query,
        items=items,
        exact_facts=exact,
        policy={
            "allow_execution": policy["allow_execution"],
            "hard_constraints": policy["hard_constraints"],
            "v_exec": policy["v_exec"],
        },
    )
    memories = []
    for symbol in packet["isymprev"]:
        row = by_id.get(symbol["id"])
        if row is None:
            continue
        memories.append({
            "id": row["id"],
            "task_key": row["task_key"],
            "option_key": row["option_key"],
            "polarity": row["polarity"],
            "source_event_ids": row["source_event_ids"],
            "updated_at": row["updated_at"],
            "content_sha256": symbol["content_sha256"],
            "stream": symbol["stream"],
            "supplied_by": "loci_engine.memory_lifecycle",
            "store_path": str(path),
        })
    return _stamp({
        **base,
        "status": "completed",
        "store_path": str(path),
        "opening_rejected": opening_rejected,
        "opening_used": usable_opening is not None,
        "memories": memories,
        "qsymprev": packet["qsymprev"],
        "symprev_status": packet["status"],
        "card_archetype": packet["archetype"],
        "card_depth_k": packet["depth_k"],
        "token_budget": packet["token_budget"],
        "policy_allow_context_inject": policy["allow_execution"],
        "embeddings_used": False,
    }, config, owner_id)


def process_turn(
    config: MemoryConfig,
    *,
    owner_id: str,
    conversation_id: str,
    text: str,
    confirmed: Optional[Dict[str, Any]] = None,
    now_day: float = 0.0,
) -> Dict[str, Any]:
    """Do not crystallize raw turn text. Only an explicit confirmed outcome is stored."""
    if not config.autoload:
        return _stamp({
            "engine": "loci_engine.memory_lifecycle",
            "status": "skipped",
            "conversation_id": conversation_id,
            "stored": False,
            "reason": "autoload off; raw text was not stored",
        }, config, owner_id)
    if confirmed is None:
        return _stamp({
            "engine": "loci_engine.memory_lifecycle",
            "status": "completed",
            "conversation_id": conversation_id,
            "stored": False,
            "reason": "turn text is not a confirmed fact",
            "text_sha256": _sha(text),
        }, config, owner_id)
    try:
        written = confirm_fact(config, owner_id=owner_id, now_day=now_day, **confirmed)
    except (sqlite3.DatabaseError, OSError, ValueError) as exc:
        return _stamp({
            "engine": "loci_engine.memory_lifecycle",
            "status": "unavailable",
            "conversation_id": conversation_id,
            "stored": False,
            "reason": f"{type(exc).__name__}: {exc}",
        }, config, owner_id)
    return _stamp({
        "engine": "loci_engine.memory_lifecycle",
        "status": "completed",
        "conversation_id": conversation_id,
        "stored": True,
        "memory": written,
    }, config, owner_id)


def conversation_end(config: MemoryConfig, *, owner_id: str, conversation_id: str) -> Dict[str, Any]:
    return _stamp({
        "engine": "loci_engine.memory_lifecycle",
        "status": "completed",
        "event": "conversation_end",
        "owner_id": owner_id,
        "conversation_id": conversation_id,
        "deleted_store": False,
    }, config, owner_id)
