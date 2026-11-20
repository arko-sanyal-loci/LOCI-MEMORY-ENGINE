"""
loci_engine/value_bus.py
========================
Value bus: exact, typed, committed values shared between parallel branches.
Companion to the heat bus (Efficiency + Guidance pillars).

Why two buses
-------------
In the Thermal Reasoning Substrate, parallel reasoning branches share a heat
map: when branch B mentions an entity it warms in the map, and branch A,
reading the map, starts retrieving the right context before B has finished.
That works for **informational** dependencies ("what does A need to know?").

It cannot work for **value** dependencies ("A needs the number B computes").
The heat map stores lossy 128-dim int8 embeddings; you can recover "something
about invoice totals is hot", never "the total is 4,217". If A reads a value
off the heat bus it gets a fuzzy neighbour and confidently produces a wrong
number. So value dependencies ride a second bus with opposite properties:
exact, typed, key-addressed slots.

Design (source: Dropbox ``Claude Artifacts/Part 2/llm parallel computer
workspace.txt``, 2026-09-07), mapped to CPU terms:

* **Scoreboarding (Tomasulo).** A consumer waits on one named slot, not on
  the producing branch finishing. ``wait()`` blocks only until that slot
  commits.
* **Result forwarding.** A stream watcher can ``propose()`` a value the
  moment it appears mid-generation, thousands of tokens before the producer
  finishes.
* **Commit semantics.** Mid-stream values are tentative (B may write 42,
  then correct itself to 47). Rolling back an LLM branch means regenerating
  it, so the bus forwards **only committed values**: a proposal becomes
  visible to ``wait()``/``get()`` only after ``commit()``, or automatically
  when its confidence reaches ``auto_commit_confidence``.
* **Asymmetric routing.** Sending a value need to the heat bus produces
  silent wrongness; sending an informational need to the value bus only
  costs a stall. So ``route()`` defaults to the value bus when uncertain,
  and uses cheap typed extraction (regex) before anything expensive.

This module is in-process and thread-safe (``threading.Condition``). It is
the reference semantics; a cross-process version can sit on the
coordination bus with the same API.
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class SlotState(str, Enum):
    EMPTY = "empty"
    TENTATIVE = "tentative"
    COMMITTED = "committed"


class Bus(str, Enum):
    VALUE = "value"
    HEAT = "heat"


class ValueBusError(Exception):
    """Type mismatch, re-commit of a different value, or similar misuse."""


@dataclass
class Slot:
    key: str
    type_: type
    state: SlotState = SlotState.EMPTY
    value: Any = None
    confidence: float = 0.0
    producer: Optional[str] = None
    committed_at: Optional[float] = None
    history: List[Tuple[float, str, Any, float]] = field(default_factory=list)


class ValueBus:
    """Typed, key-addressed slots with commit-only forwarding."""

    def __init__(self, auto_commit_confidence: Optional[float] = 0.95):
        self._slots: Dict[str, Slot] = {}
        self._cv = threading.Condition()
        self.auto_commit_confidence = auto_commit_confidence

    # -- declaration -------------------------------------------------------
    def declare(self, key: str, type_: type = object) -> Slot:
        """Declare a slot. Re-declaring with the same type is a no-op."""
        with self._cv:
            slot = self._slots.get(key)
            if slot is None:
                slot = self._slots[key] = Slot(key=key, type_=type_)
            elif slot.type_ is not type_ and type_ is not object:
                raise ValueBusError(f"slot {key!r} already declared as {slot.type_.__name__}")
            return slot

    def _check_type(self, slot: Slot, value: Any) -> Any:
        if slot.type_ is object or isinstance(value, slot.type_):
            return value
        try:
            return slot.type_(value)
        except (TypeError, ValueError) as exc:
            raise ValueBusError(
                f"slot {slot.key!r} expects {slot.type_.__name__}, got {value!r}"
            ) from exc

    # -- producer side -----------------------------------------------------
    def propose(self, key: str, value: Any, *, confidence: float = 0.5,
                producer: Optional[str] = None) -> SlotState:
        """Record a tentative value (e.g. extracted mid-stream).

        Tentative values are NOT visible to consumers. A later proposal
        replaces an earlier one (the producer revised itself). If
        ``confidence >= auto_commit_confidence`` the value commits at once.
        """
        with self._cv:
            slot = self._slots.get(key) or self.declare(key)
            if slot.state is SlotState.COMMITTED:
                if slot.value == self._check_type(slot, value):
                    return slot.state
                raise ValueBusError(f"slot {key!r} is committed; open a new key to revise")
            slot.value = self._check_type(slot, value)
            slot.confidence = confidence
            slot.producer = producer
            slot.state = SlotState.TENTATIVE
            slot.history.append((time.time(), "propose", slot.value, confidence))
            if self.auto_commit_confidence is not None and confidence >= self.auto_commit_confidence:
                return self._commit_locked(slot)
            return slot.state

    def commit(self, key: str, value: Any = None, *, producer: Optional[str] = None) -> SlotState:
        """Mark a slot final and wake every waiter.

        With ``value`` given, commits that value directly; otherwise commits
        the current tentative value. Committing twice with the same value is
        idempotent; with a different value it raises.
        """
        with self._cv:
            slot = self._slots.get(key) or self.declare(key)
            if value is not None:
                value = self._check_type(slot, value)
                if slot.state is SlotState.COMMITTED and slot.value != value:
                    raise ValueBusError(f"slot {key!r} already committed to {slot.value!r}")
                slot.value = value
                slot.confidence = max(slot.confidence, 1.0)
                slot.producer = producer or slot.producer
            elif slot.state is SlotState.EMPTY:
                raise ValueBusError(f"slot {key!r} has nothing to commit")
            return self._commit_locked(slot)

    def _commit_locked(self, slot: Slot) -> SlotState:
        if slot.state is not SlotState.COMMITTED:
            slot.state = SlotState.COMMITTED
            slot.committed_at = time.time()
            slot.history.append((slot.committed_at, "commit", slot.value, slot.confidence))
            self._cv.notify_all()
        return slot.state

    # -- consumer side -----------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        """Committed value, or ``default``. Never returns a tentative value."""
        with self._cv:
            slot = self._slots.get(key)
            return slot.value if slot and slot.state is SlotState.COMMITTED else default

    def wait(self, key: str, timeout: Optional[float] = None) -> Any:
        """Block until ``key`` commits (scoreboard stall on one slot only).

        Raises ``TimeoutError`` if it does not commit in time.
        """
        deadline = None if timeout is None else time.monotonic() + timeout
        with self._cv:
            self._slots.get(key) or self.declare(key)
            while self._slots[key].state is not SlotState.COMMITTED:
                remaining = None if deadline is None else deadline - time.monotonic()
                if remaining is not None and remaining <= 0:
                    raise TimeoutError(f"value slot {key!r} not committed within {timeout}s")
                self._cv.wait(remaining)
            return self._slots[key].value

    def state(self, key: str) -> SlotState:
        with self._cv:
            slot = self._slots.get(key)
            return slot.state if slot else SlotState.EMPTY

    def snapshot(self) -> Dict[str, dict]:
        """Committed values only, for logging or handing to another process."""
        with self._cv:
            return {k: {"value": s.value, "type": s.type_.__name__, "producer": s.producer,
                        "committed_at": s.committed_at}
                    for k, s in self._slots.items() if s.state is SlotState.COMMITTED}


# ---------------------------------------------------------------------------
# Stream watcher: typed extraction for early forwarding
# ---------------------------------------------------------------------------

# "<key> = <value>" / "<key>: <value>" / "<key> is <value>", value numeric or id-like.
_ASSIGN = re.compile(
    r"\b(?P<key>[A-Za-z_][\w.\-]{0,63})\s*(?:=|:|\bis\b)\s*"
    r"(?P<val>-?\d[\d,]*(?:\.\d+)?|[0-9a-f]{7,40}|v?\d+\.\d+(?:\.\d+)?)\b"
)
_FINAL_MARK = re.compile(r"\b(final(?:ly)?|answer|result|committed|therefore)\b", re.I)


def _coerce(raw: str) -> Any:
    s = raw.replace(",", "")
    try:
        return int(s)
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return raw


def watch_stream(bus: ValueBus, text: str, *, producer: Optional[str] = None,
                 keys: Optional[List[str]] = None) -> List[Tuple[str, Any, SlotState]]:
    """Extract ``key = value`` assignments from a chunk of a branch's output.

    Values found in a sentence that also carries a finality marker
    ("final", "answer", "therefore", ...) are proposed at confidence 0.95
    (auto-commit by default); others at 0.6 (tentative). Restrict to
    declared ``keys`` to avoid picking up incidental numbers.
    """
    found = []
    for sentence in re.split(r"(?<=[.!?\n])\s+", text):
        final = bool(_FINAL_MARK.search(sentence))
        for m in _ASSIGN.finditer(sentence):
            key = m.group("key")
            if keys is not None and key not in keys:
                continue
            value = _coerce(m.group("val"))
            st = bus.propose(key, value, confidence=0.95 if final else 0.6, producer=producer)
            found.append((key, value, st))
    return found


# ---------------------------------------------------------------------------
# Router: which bus does a dependency need?
# ---------------------------------------------------------------------------

_VALUE_CUES = re.compile(
    r"\b(how (many|much)|what (is|was) the (number|total|count|value|price|port|id|version|date)"
    r"|exact|compute|calculate|sum|total|amount|port|version|hash|id\b|date|price|\d)", re.I)
_INFO_CUES = re.compile(
    r"\b(why|explain|describe|context|background|overview|summar|related|about|relevant)\b", re.I)


def route(need: str, *, classifier: Optional[Callable[[str], Optional[Bus]]] = None) -> Bus:
    """Pick the bus for a dependency description.

    Cheap regex first; an optional ``classifier`` (e.g. an LLM call) is
    consulted only when the regex is ambiguous. When still uncertain the
    answer is the VALUE bus: a needless stall is recoverable, a wrong number
    is not.
    """
    v, i = bool(_VALUE_CUES.search(need)), bool(_INFO_CUES.search(need))
    if v and not i:
        return Bus.VALUE
    if i and not v:
        return Bus.HEAT
    if classifier is not None:
        choice = classifier(need)
        if choice in (Bus.VALUE, Bus.HEAT):
            return choice
    return Bus.VALUE


__all__ = ["Bus", "Slot", "SlotState", "ValueBus", "ValueBusError", "route", "watch_stream"]
