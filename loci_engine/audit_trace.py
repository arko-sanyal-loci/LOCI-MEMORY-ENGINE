#!/usr/bin/env python3
"""Append-only step trace for one learning-cycle run.

Each step stores a timezone-aware wall-clock start and end, a monotonic
duration, status, and SHA-256 digests of the input and output summaries.
The file is hash-chained. That chain can show whether this file was edited
after it was written. It does not prove the wall clock was honest, does not
prove a third party watched the run, and a completely replaced file can
carry its own valid chain. No remote attestation service is used.
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


LIMITATION = (
    "Timestamps and the hash chain are local tamper evidence for this file. "
    "They do not prove wall-clock time, do not prove the run was observed live, "
    "and cannot stop someone from substituting a different complete log. "
    "No third-party attestation or signing key is configured."
)
GENESIS = "0" * 64


def digest(payload: Any) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _canonical(record: Dict[str, Any]) -> str:
    body = {key: value for key, value in record.items() if key != "record_hash"}
    return json.dumps(body, sort_keys=True, default=str, separators=(",", ":"))


class AuditTrace:
    def __init__(self, path: str, *, config: Optional[Dict[str, Any]] = None, code_version: str = "unknown"):
        self.path = Path(path)
        self.run_id = f"run_{uuid.uuid4().hex[:12]}"
        self.code_version = code_version
        self.config = dict(config or {})
        self._prev = GENESIS
        self._index = 0
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.exists():
            raise FileExistsError(f"audit trace already exists: {self.path}")
        self._append(
            {
                "kind": "header",
                "run_id": self.run_id,
                "code_version": self.code_version,
                "config_sha256": digest(self.config),
                "config": self.config,
                "limitation": LIMITATION,
                "attestation": None,
                "wall_start": datetime.now(timezone.utc).isoformat(),
                "status": "opened",
            }
        )

    @contextmanager
    def step(self, name: str, inputs: Optional[Dict[str, Any]] = None) -> Iterator[Dict[str, Any]]:
        holder: Dict[str, Any] = {"output": None, "status": "completed"}
        wall_start = datetime.now(timezone.utc)
        mono_start = time.perf_counter()
        try:
            yield holder
        except Exception as exc:
            self._close_step(
                name=name,
                inputs=inputs or {},
                output={"error": type(exc).__name__},
                status="error",
                wall_start=wall_start,
                mono_start=mono_start,
                error_type=type(exc).__name__,
            )
            raise
        else:
            status = str(holder.get("status") or "completed")
            if status == "completed" and holder.get("output") is None and holder.get("allow_empty") is not True:
                status = holder.get("status") or "completed"
            self._close_step(
                name=name,
                inputs=inputs or {},
                output=holder.get("output"),
                status=status,
                wall_start=wall_start,
                mono_start=mono_start,
                error_type=None,
            )

    def skip(self, name: str, reason: str) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        mono = time.perf_counter()
        return self._close_step(
            name=name,
            inputs={"reason": reason},
            output={"skipped": True},
            status="skipped",
            wall_start=now,
            mono_start=mono,
            error_type=None,
            duration_override=0.0,
        )

    def _close_step(
        self,
        *,
        name: str,
        inputs: Dict[str, Any],
        output: Any,
        status: str,
        wall_start: datetime,
        mono_start: float,
        error_type: Optional[str],
        duration_override: Optional[float] = None,
    ) -> Dict[str, Any]:
        wall_end = datetime.now(timezone.utc)
        duration = time.perf_counter() - mono_start if duration_override is None else duration_override
        record = {
            "kind": "step",
            "run_id": self.run_id,
            "step_id": f"{self.run_id}_s{self._index:02d}",
            "name": name,
            "status": status,
            "wall_start": wall_start.isoformat(),
            "wall_end": wall_end.isoformat(),
            "timezone": "UTC",
            "monotonic_duration_seconds": duration,
            "input_sha256": digest(inputs),
            "output_sha256": digest(output),
            "error_type": error_type,
            "code_version": self.code_version,
        }
        return self._append(record)

    def _append(self, record: Dict[str, Any]) -> Dict[str, Any]:
        record = dict(record)
        record["prev_hash"] = self._prev
        record["record_hash"] = hashlib.sha256(
            f"{self._prev}|{_canonical(record)}".encode("utf-8")
        ).hexdigest()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str))
            handle.write("\n")
        self._prev = record["record_hash"]
        self._index += 1
        return record

    def records(self) -> List[Dict[str, Any]]:
        rows = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
        return rows


def verify_chain(path: str) -> Dict[str, Any]:
    """Check the file's internal links. A matching chain is not a clock proof."""
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    prev = GENESIS
    for index, row in enumerate(rows):
        claimed_prev = row.get("prev_hash")
        claimed = row.get("record_hash")
        expect = hashlib.sha256(f"{prev}|{_canonical(row)}".encode("utf-8")).hexdigest()
        if claimed_prev != prev or claimed != expect:
            return {"ok": False, "failed_index": index, "proves_wall_clock": False}
        prev = claimed
    return {
        "ok": True,
        "records": len(rows),
        "proves_wall_clock": False,
        "proves_live_observation": False,
        "limitation": LIMITATION,
    }
