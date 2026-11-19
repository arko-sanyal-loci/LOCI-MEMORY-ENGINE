#!/usr/bin/env python3
"""
loci_engine/provenance_biometrics.py — Multimodal Provenance Engine.
Factors: keystroke dynamics (IKI, dwell), typing cadence (WPM, pause_ratio),
spelling deviation (correction_rate). Raises ProvenanceAnomalyEvent at 1.8s
(soft) / 3.2s (hard). restriction_delta fed to governance.py SPVG consent.
"""
from __future__ import annotations
import math
import statistics
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

MIN_ENROLLMENT_EVENTS = 20
ANOMALY_THRESHOLD_SOFT = 1.8
ANOMALY_THRESHOLD_HARD = 3.2
MAX_PROFILE_WINDOW = 500


@dataclass
class KeyEvent:
    key: str
    timestamp_ms: float
    event_type: str  # "down" | "up"


@dataclass
class SpellingCorrection:
    original: str
    corrected: str
    method: str = "backspace"


@dataclass
class ProvenanceAnomalyEvent:
    session_id: str
    factor: str
    z_score: float
    baseline_mean: float
    observed_value: float
    severity: str  # "soft" | "hard"
    restriction_delta: float
    timestamp_ms: float = field(default_factory=lambda: time.time() * 1000)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "factor": self.factor,
            "z_score": round(self.z_score, 4),
            "baseline_mean": round(self.baseline_mean, 4),
            "observed_value": round(self.observed_value, 4),
            "severity": self.severity,
            "restriction_delta": round(self.restriction_delta, 4),
            "timestamp_ms": self.timestamp_ms,
        }


@dataclass
class BiometricProfile:
    session_id: str
    enrolled: bool = False
    enrollment_count: int = 0
    iki_mean: float = 0.0
    iki_std: float = 1.0
    dwell_mean: float = 0.0
    dwell_std: float = 1.0
    wpm_mean: float = 0.0
    wpm_std: float = 1.0
    pause_ratio_mean: float = 0.0
    pause_ratio_std: float = 1.0
    correction_rate_mean: float = 0.0
    correction_rate_std: float = 1.0

    def factor_z(self, factor: str, observed: float) -> float:
        means = {"iki": self.iki_mean, "dwell": self.dwell_mean,
                 "wpm": self.wpm_mean, "pause_ratio": self.pause_ratio_mean,
                 "correction_rate": self.correction_rate_mean}
        stds = {"iki": self.iki_std, "dwell": self.dwell_std,
                "wpm": self.wpm_std, "pause_ratio": self.pause_ratio_std,
                "correction_rate": self.correction_rate_std}
        std = stds.get(factor, 1.0)
        if std < 1e-6:
            std = 1e-6
        return abs(observed - means.get(factor, observed)) / std


class KeystrokeDynamicsComputer:
    @staticmethod
    def compute(events: List[KeyEvent]) -> Tuple[List[float], List[float]]:
        downs: Dict[str, float] = {}
        ikis: List[float] = []
        dwells: List[float] = []
        last_down: Optional[float] = None
        for ev in sorted(events, key=lambda e: e.timestamp_ms):
            if ev.event_type == "down":
                if last_down is not None:
                    iki = ev.timestamp_ms - last_down
                    if 20 < iki < 2000:
                        ikis.append(iki)
                downs[ev.key] = ev.timestamp_ms
                last_down = ev.timestamp_ms
            elif ev.event_type == "up":
                if ev.key in downs:
                    dwell = ev.timestamp_ms - downs.pop(ev.key)
                    if 10 < dwell < 500:
                        dwells.append(dwell)
        return ikis, dwells

    @staticmethod
    def safe_stats(values: List[float]) -> Tuple[float, float]:
        if not values:
            return 0.0, 1.0
        mean = statistics.mean(values)
        std = statistics.stdev(values) if len(values) > 1 else 1.0
        return mean, max(std, 1e-6)


class TypingCadenceComputer:
    PAUSE_THRESHOLD_MS = 500.0
    CHARS_PER_WORD = 5.0

    @staticmethod
    def compute(events: List[KeyEvent]) -> Tuple[float, float]:
        downs = sorted([e for e in events if e.event_type == "down"],
                       key=lambda e: e.timestamp_ms)
        if len(downs) < 5:
            return 0.0, 0.0
        total_ms = downs[-1].timestamp_ms - downs[0].timestamp_ms
        if total_ms < 100:
            return 0.0, 0.0
        gaps = [downs[i+1].timestamp_ms - downs[i].timestamp_ms for i in range(len(downs)-1)]
        pause_ms = sum(g for g in gaps if g > TypingCadenceComputer.PAUSE_THRESHOLD_MS)
        pause_ratio = pause_ms / total_ms if total_ms > 0 else 0.0
        active_ms = total_ms - pause_ms
        chars = len(downs)
        wpm = (chars / TypingCadenceComputer.CHARS_PER_WORD) / (active_ms / 60000.0) if active_ms > 0 else 0.0
        return round(min(wpm, 300.0), 2), round(min(pause_ratio, 1.0), 4)


class SpellingDeviationComputer:
    @staticmethod
    def compute(corrections: List[SpellingCorrection], total_chars: int) -> float:
        if total_chars < 10:
            return 0.0
        return (len(corrections) / total_chars) * 100.0


class ProvenanceBiometricEngine:
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.profile = BiometricProfile(session_id=session_id)
        self._key_buffer: List[KeyEvent] = []
        self._correction_buffer: List[SpellingCorrection] = []
        self._total_chars: int = 0
        self._anomaly_history: List[ProvenanceAnomalyEvent] = []

    def record_keyevent(self, event: KeyEvent) -> None:
        self._key_buffer.append(event)
        if event.event_type == "down":
            self._total_chars += 1
        if len(self._key_buffer) > MAX_PROFILE_WINDOW * 2:
            self._key_buffer = self._key_buffer[-MAX_PROFILE_WINDOW:]

    def record_correction(self, correction: SpellingCorrection) -> None:
        self._correction_buffer.append(correction)

    def _compute_current_factors(self) -> Dict[str, float]:
        ikis, dwells = KeystrokeDynamicsComputer.compute(self._key_buffer)
        wpm, pause_ratio = TypingCadenceComputer.compute(self._key_buffer)
        correction_rate = SpellingDeviationComputer.compute(self._correction_buffer, self._total_chars)
        iki_mean, _ = KeystrokeDynamicsComputer.safe_stats(ikis)
        dwell_mean, _ = KeystrokeDynamicsComputer.safe_stats(dwells)
        return {"iki": iki_mean, "dwell": dwell_mean, "wpm": wpm,
                "pause_ratio": pause_ratio, "correction_rate": correction_rate}

    def enroll(self) -> Dict[str, Any]:
        if self._total_chars < MIN_ENROLLMENT_EVENTS:
            return {"enrolled": False, "reason": f"need {MIN_ENROLLMENT_EVENTS} events, have {self._total_chars}"}
        ikis, dwells = KeystrokeDynamicsComputer.compute(self._key_buffer)
        wpm, pause_ratio = TypingCadenceComputer.compute(self._key_buffer)
        correction_rate = SpellingDeviationComputer.compute(self._correction_buffer, self._total_chars)
        iki_mean, iki_std = KeystrokeDynamicsComputer.safe_stats(ikis)
        dwell_mean, dwell_std = KeystrokeDynamicsComputer.safe_stats(dwells)
        self.profile.iki_mean = iki_mean
        self.profile.iki_std = iki_std
        self.profile.dwell_mean = dwell_mean
        self.profile.dwell_std = dwell_std
        self.profile.wpm_mean = wpm
        self.profile.wpm_std = max(wpm * 0.15, 5.0)
        self.profile.pause_ratio_mean = pause_ratio
        self.profile.pause_ratio_std = max(pause_ratio * 0.20, 0.05)
        self.profile.correction_rate_mean = correction_rate
        self.profile.correction_rate_std = max(correction_rate * 0.25, 0.5)
        self.profile.enrolled = True
        self.profile.enrollment_count = self._total_chars
        self._log_glassbox("enrolled", {"enrollment_chars": self._total_chars})
        return {"enrolled": True, "session_id": self.session_id, "factors": self._compute_current_factors()}

    def verify(self) -> Dict[str, Any]:
        if not self.profile.enrolled:
            return {"verified": False, "reason": "not_enrolled", "anomalies": [], "restriction_delta": 0.0}
        factors = self._compute_current_factors()
        anomalies: List[ProvenanceAnomalyEvent] = []
        total_restriction = 0.0
        for factor, observed in factors.items():
            if observed == 0.0:
                continue
            z = self.profile.factor_z(factor, observed)
            if z >= ANOMALY_THRESHOLD_SOFT:
                severity = "hard" if z >= ANOMALY_THRESHOLD_HARD else "soft"
                per_sigma = 0.15 if severity == "hard" else 0.08
                excess = z - (ANOMALY_THRESHOLD_HARD if severity == "hard" else ANOMALY_THRESHOLD_SOFT)
                delta = min(per_sigma * (1.0 + excess), 0.40)
                ev = ProvenanceAnomalyEvent(
                    session_id=self.session_id, factor=factor, z_score=z,
                    baseline_mean=getattr(self.profile, f"{factor}_mean", 0.0),
                    observed_value=observed, severity=severity, restriction_delta=delta,
                )
                anomalies.append(ev)
                self._anomaly_history.append(ev)
                total_restriction += delta
        total_restriction = min(total_restriction, 0.80)
        if anomalies:
            self._log_glassbox("anomaly_detected", {
                "factor_count": len(anomalies), "restriction_delta": total_restriction,
                "severities": [a.severity for a in anomalies],
            })
        return {
            "verified": True, "session_id": self.session_id, "factors": factors,
            "anomalies": [a.to_dict() for a in anomalies],
            "restriction_delta": round(total_restriction, 4),
            "composite_z": round(math.sqrt(sum(a.z_score**2 for a in anomalies)) if anomalies else 0.0, 4),
        }

    def get_restriction_delta(self) -> float:
        if not self.profile.enrolled or not self._anomaly_history:
            return 0.0
        recent = self._anomaly_history[-10:]
        return min(sum(a.restriction_delta for a in recent), 0.80)

    def _log_glassbox(self, event_type: str, metadata: Dict[str, Any]) -> None:
        try:
            from loci_engine.glassbox import glassbox_learn
            glassbox_learn(
                author_id=f"provenance:{self.session_id}",
                role_tag="provenance_biometrics",
                content=f"[{event_type}] session={self.session_id} meta={metadata}",
                category="provenance", metadata=metadata,
            )
        except Exception:
            pass


_ENGINES: Dict[str, ProvenanceBiometricEngine] = {}


def get_engine(session_id: str) -> ProvenanceBiometricEngine:
    if session_id not in _ENGINES:
        _ENGINES[session_id] = ProvenanceBiometricEngine(session_id)
    return _ENGINES[session_id]


def record_keyevent(session_id: str, key: str, timestamp_ms: float, event_type: str = "down") -> None:
    get_engine(session_id).record_keyevent(KeyEvent(key=key, timestamp_ms=timestamp_ms, event_type=event_type))


def record_correction(session_id: str, original: str, corrected: str, method: str = "backspace") -> None:
    get_engine(session_id).record_correction(SpellingCorrection(original=original, corrected=corrected, method=method))


def enroll_session(session_id: str) -> Dict[str, Any]:
    return get_engine(session_id).enroll()


def verify_session(session_id: str) -> Dict[str, Any]:
    return get_engine(session_id).verify()


def get_restriction_delta(session_id: str) -> float:
    return get_engine(session_id).get_restriction_delta()
