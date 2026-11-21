"""Consent-gated, append-only profile journal for derived stream features.

The journal is intentionally a separate SQLite file from the LOCI fact store.
It accepts compact, already-derived categorical features only: callers must not
send prompts, transcripts, audio samples, frames, or precise locations here.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import math
import re
import sqlite3
import time
from typing import Any
import uuid

GENESIS_HASH = hashlib.sha256(b"LOCI_RAG_APPENDIX_JOURNAL_V1").hexdigest()
SCOPES = {"environment", "user"}
TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9_.:-]{0,63}$")


class ConsentRequired(PermissionError):
    """Raised when profile data is written or read without active consent."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _token(value: str, field: str) -> str:
    normalized = value.strip().lower()
    if not TOKEN_RE.fullmatch(normalized):
        raise ValueError(f"{field} must be a short categorical token (no free text)")
    return normalized


class RagAppendixJournal:
    """Versioned evidence and profile journal, gated by per-scope consent.

    Consent is off by default. A new consent period gets a new version so old
    evidence is not silently reused after consent is withdrawn and later renewed.
    Updates and deletes to journal entries are rejected by SQLite triggers.
    """

    def __init__(self, path: str, *, half_life_days: float = 30.0) -> None:
        if not math.isfinite(half_life_days) or half_life_days <= 0:
            raise ValueError("half_life_days must be positive and finite")
        self.half_life_days = half_life_days
        self.conn = sqlite3.connect(path, timeout=10, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS journal_events (
                seq INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_type TEXT NOT NULL,
                scope TEXT NOT NULL,
                consent_version INTEGER NOT NULL,
                occurred_at REAL NOT NULL,
                payload_json TEXT NOT NULL,
                prev_hash TEXT NOT NULL,
                event_hash TEXT NOT NULL UNIQUE
            );
            CREATE INDEX IF NOT EXISTS idx_journal_scope_type_seq
                ON journal_events(scope, event_type, seq);
            CREATE TRIGGER IF NOT EXISTS journal_events_no_update
                BEFORE UPDATE ON journal_events BEGIN
                    SELECT RAISE(ABORT, 'journal is append-only');
                END;
            CREATE TRIGGER IF NOT EXISTS journal_events_no_delete
                BEFORE DELETE ON journal_events BEGIN
                    SELECT RAISE(ABORT, 'journal is append-only');
                END;
            """
        )

    def close(self) -> None:
        self.conn.close()

    def _state(self, scope: str) -> tuple[bool, int]:
        row = self.conn.execute(
            "SELECT event_type, consent_version FROM journal_events "
            "WHERE scope = ? AND event_type IN ('consent_granted', 'consent_revoked') "
            "ORDER BY seq DESC LIMIT 1", (scope,),
        ).fetchone()
        if row is None:
            return False, 0
        return row["event_type"] == "consent_granted", row["consent_version"]

    def _append(self, event_type: str, scope: str, consent_version: int,
                payload: dict[str, Any], occurred_at: float | None = None,
                *, require_active_consent: bool = False) -> dict[str, Any]:
        at = time.time() if occurred_at is None else float(occurred_at)
        if not math.isfinite(at):
            raise ValueError("occurred_at must be finite")
        payload_json = _canonical(payload)
        event_id = str(uuid.uuid4())
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            if require_active_consent:
                state = self.conn.execute(
                    "SELECT event_type, consent_version FROM journal_events "
                    "WHERE scope=? AND event_type IN ('consent_granted','consent_revoked') "
                    "ORDER BY seq DESC LIMIT 1", (scope,),
                ).fetchone()
                if (state is None or state["event_type"] != "consent_granted"
                        or state["consent_version"] != consent_version):
                    raise ConsentRequired(f"active {scope} consent is required")
            row = self.conn.execute(
                "SELECT event_hash FROM journal_events ORDER BY seq DESC LIMIT 1"
            ).fetchone()
            prev_hash = row["event_hash"] if row else GENESIS_HASH
            body = {
                "event_id": event_id, "event_type": event_type, "scope": scope,
                "consent_version": consent_version, "occurred_at": at,
                "payload": payload, "prev_hash": prev_hash,
            }
            event_hash = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
            cursor = self.conn.execute(
                "INSERT INTO journal_events(event_id,event_type,scope,consent_version,"
                "occurred_at,payload_json,prev_hash,event_hash) VALUES(?,?,?,?,?,?,?,?)",
                (event_id, event_type, scope, consent_version, at, payload_json,
                 prev_hash, event_hash),
            )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise
        return {"seq": cursor.lastrowid, **body, "event_hash": event_hash}

    def grant_consent(self, scope: str, *, purpose: str = "profile_patterns",
                      occurred_at: float | None = None) -> dict[str, Any]:
        """Record explicit user consent for one profile scope."""
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {sorted(SCOPES)}")
        purpose = _token(purpose, "purpose")
        granted, version = self._state(scope)
        if granted:
            return {"already_granted": True, "scope": scope, "consent_version": version}
        return self._append("consent_granted", scope, version + 1,
                            {"purpose": purpose}, occurred_at)

    def revoke_consent(self, scope: str, *, occurred_at: float | None = None) -> dict[str, Any]:
        """Stop future collection and profile reads; preserve the audit trail."""
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {sorted(SCOPES)}")
        granted, version = self._state(scope)
        if not granted:
            return {"already_revoked": True, "scope": scope, "consent_version": version}
        return self._append("consent_revoked", scope, version,
                            {"reason": "user_withdrew_consent"}, occurred_at)

    def consent_status(self) -> dict[str, dict[str, Any]]:
        return {scope: {"granted": self._state(scope)[0],
                        "consent_version": self._state(scope)[1]}
                for scope in sorted(SCOPES)}

    def append_features(self, scope: str, features: dict[str, str | int | float | bool],
                        *, source: str, occurred_at: float | None = None) -> dict[str, Any]:
        """Append one derived feature observation after scope consent is granted.

        Values are categorical labels, not source media or free-form text. A
        caller should quantize measurements (for example ``noise:medium``)
        before calling this method.
        """
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {sorted(SCOPES)}")
        granted, version = self._state(scope)
        if not granted:
            raise ConsentRequired(f"active {scope} consent is required")
        source = _token(source, "source")
        if not isinstance(features, dict) or not features:
            raise ValueError("features must be a non-empty mapping")
        normalized: dict[str, str] = {}
        for raw_key, raw_value in features.items():
            key = _token(raw_key, "feature")
            if isinstance(raw_value, bool):
                value = "true" if raw_value else "false"
            elif isinstance(raw_value, (int, float)):
                if not math.isfinite(float(raw_value)):
                    raise ValueError("numeric feature values must be finite")
                number = f"{float(raw_value):.3f}".replace("-", "m").replace(".", "p")
                value = _token(f"num_{number}", "feature value")
            elif isinstance(raw_value, str):
                value = _token(raw_value, "feature value")
            else:
                raise ValueError("feature values must be categorical scalars")
            normalized[key] = value
        return self._append("feature_observation", scope, version,
                            {"source": source, "features": normalized}, occurred_at,
                            require_active_consent=True)

    def append_stream_event(self, event: dict[str, Any], *,
                            session_started_at: float | None = None) -> dict[str, Any] | None:
        """Store a privacy-reduced audio/video timeline feature under environment consent.

        Captions, transcripts, score tracks, frame pixels, and object identifiers
        are deliberately ignored. Unsupported or uninformative packets return
        ``None`` and are not journaled.
        """
        if not isinstance(event, dict) or event.get("track") not in {"audio", "video"}:
            return None
        data = event.get("data")
        if not isinstance(data, dict):
            return None
        features: dict[str, str] = {}
        if event["track"] == "audio":
            rms = data.get("rms")
            if isinstance(rms, (int, float)) and math.isfinite(float(rms)) and rms >= 0:
                features["audio_level"] = (
                    "silence" if rms < 0.003 else "quiet" if rms < 0.02
                    else "moderate" if rms < 0.12 else "loud"
                )
            centroid = data.get("spectral_centroid_hz")
            if isinstance(centroid, (int, float)) and math.isfinite(float(centroid)) and centroid >= 0:
                features["audio_timbre_band"] = (
                    "low" if centroid < 500 else "mid" if centroid < 2000 else "high"
                )
            source = "audio_stream"
        else:
            fidelity = data.get("fidelity")
            if fidelity in {"cold", "warm", "hot"}:
                features["visual_fidelity"] = fidelity
            if isinstance(data.get("change_reasons"), list):
                features["visual_change"] = "change" if data["change_reasons"] else "stable"
            families = data.get("families")
            motion = families.get("motion") if isinstance(families, dict) else None
            speed = motion.get("screen_speed") if isinstance(motion, dict) else None
            if isinstance(speed, (int, float)) and math.isfinite(float(speed)) and speed >= 0:
                features["visual_motion"] = (
                    "still" if speed < 0.01 else "slow" if speed < 0.1
                    else "moving" if speed < 0.45 else "fast"
                )
            source = "video_stream"
        if not features:
            return None
        pts_us = event.get("pts_us")
        occurred_at = time.time()
        if (session_started_at is not None and isinstance(pts_us, (int, float))
                and math.isfinite(float(pts_us))):
            occurred_at = float(session_started_at) + float(pts_us) / 1_000_000
        return self.append_features("environment", features, source=source,
                                    occurred_at=occurred_at)

    def build_profile(self, scope: str, *, now: float | None = None,
                      min_support: int = 3) -> dict[str, Any] | None:
        """Build and append a heat-weighted profile from the current consent epoch."""
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {sorted(SCOPES)}")
        granted, version = self._state(scope)
        if not granted:
            raise ConsentRequired(f"active {scope} consent is required")
        if min_support < 2:
            raise ValueError("min_support must be at least 2")
        current_time = time.time() if now is None else float(now)
        if not math.isfinite(current_time):
            raise ValueError("now must be finite")
        rows = self.conn.execute(
            "SELECT occurred_at,payload_json FROM journal_events WHERE scope=? "
            "AND event_type='feature_observation' AND consent_version=? ORDER BY seq",
            (scope, version),
        ).fetchall()
        heatmap: dict[tuple[str, str], list[float]] = defaultdict(list)
        for row in rows:
            age_days = max(0.0, (current_time - row["occurred_at"]) / 86400.0)
            weight = math.exp(-math.log(2) * age_days / self.half_life_days)
            for key, value in json.loads(row["payload_json"])["features"].items():
                heatmap[(key, value)].append(weight)
        patterns = []
        for (feature, value), weights in sorted(heatmap.items()):
            support = len(weights)
            heat = sum(weights)
            confidence = 1.0 - math.exp(-heat / 3.0)
            if support >= min_support and confidence >= 0.60:
                patterns.append({"feature": feature, "value": value, "support": support,
                                 "heat": round(heat, 6), "confidence": round(confidence, 6)})
        if not patterns:
            return None
        prior = self.conn.execute(
            "SELECT event_id FROM journal_events WHERE scope=? AND event_type='profile_version' "
            "AND consent_version=? ORDER BY seq DESC LIMIT 1", (scope, version),
        ).fetchone()
        payload = {"patterns": patterns, "observation_count": len(rows),
                   "heat_half_life_days": self.half_life_days,
                   "supersedes_id": prior["event_id"] if prior else None}
        return self._append("profile_version", scope, version, payload, current_time,
                            require_active_consent=True)

    def get_profile(self, scope: str) -> dict[str, Any] | None:
        granted, version = self._state(scope)
        if not granted:
            return None
        row = self.conn.execute(
            "SELECT * FROM journal_events WHERE scope=? AND event_type='profile_version' "
            "AND consent_version=? ORDER BY seq DESC LIMIT 1", (scope, version),
        ).fetchone()
        if row is None:
            return None
        return {"event_id": row["event_id"], "scope": scope,
                "consent_version": version, "version": row["seq"],
                **json.loads(row["payload_json"])}

    def verify_chain(self) -> dict[str, Any]:
        rows = self.conn.execute("SELECT * FROM journal_events ORDER BY seq").fetchall()
        previous = GENESIS_HASH
        for row in rows:
            payload = json.loads(row["payload_json"])
            body = {"event_id": row["event_id"], "event_type": row["event_type"],
                    "scope": row["scope"], "consent_version": row["consent_version"],
                    "occurred_at": row["occurred_at"], "payload": payload,
                    "prev_hash": previous}
            calculated = hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()
            if row["prev_hash"] != previous or row["event_hash"] != calculated:
                return {"valid": False, "entries": len(rows), "bad_seq": row["seq"]}
            previous = row["event_hash"]
        return {"valid": True, "entries": len(rows), "tail_hash": previous}


__all__ = ["ConsentRequired", "RagAppendixJournal"]
