"""
LOCI Unified SymPrev Architecture & Taxonomy
Canonical Naming Invariants:
- Engine: LOCI (never Loki / Lokie)
- Substrate / AI Core: Arc (never Ark)

SymPrev Family:
1. ISymPrev: Information SymLink Preview (Narrative, episodic, associative graph)
2. QSymPrev (Versioned): Quantified SymLink Preview (Roza & Arc anti-hallucination mechanism)
3. DSymPrev: Dream SymLink Preview (Counterfactual reflection sandbox)
4. MSymPrev: Mood SymLink Preview (Quality of Life engine & affective trajectory)
5. SSymPrev: Simulation SymLink Preview (Golden extracted simulation rollouts feeding Dream Worker)
"""

from dataclasses import dataclass, field
from enum import Enum
import time
from typing import Any, Dict, Optional

class SymPrevType(str, Enum):
    ISYMPREV = "ISymPrev"  # Qualitative narrative
    QSYMPREV = "QSymPrev"  # Versioned exact facts (Roza & Arc)
    DSYMPREV = "DSymPrev"  # Dream & counterfactual sandbox
    MSYMPREV = "MSymPrev"  # Affective mood & distress trajectory
    SSYMPREV = "SSymPrev"  # Golden simulation extracts

@dataclass
class VersionedInterval:
    valid_from: float
    valid_until: Optional[float] = None  # None = currently active
    superseded_by: Optional[str] = None

@dataclass
class QSymPrevNode:
    """Roza & Arc's Versioned Anti-Hallucination Mechanism."""
    fact_key: str
    value: Any
    interval: VersionedInterval
    is_deterministic: bool
    recompute_rate: Optional[float] = None
    last_verified_ts: float = field(default_factory=time.time)

    def resolve(self, current_ts: float) -> str:
        if self.is_deterministic and self.recompute_rate is not None:
            elapsed = current_ts - self.interval.valid_from
            current_val = self.value + self.recompute_rate * elapsed
            return f"{current_val:.2f} (dynamically recomputed)"
        if self.interval.valid_until and current_ts > self.interval.valid_until:
            return f"EXPIRED: Stale as of {self.interval.valid_until} (was {self.value})"
        return f"{self.value} (exact canonical fact)"

@dataclass
class MSymPrevNode:
    """Mood SymLink Preview tied to Quality of Life Engine."""
    raw_utterance: str
    valence: float   # [-1.0, 1.0]
    arousal: float   # [0.0, 1.0]
    dominance: float # [0.0, 1.0]
    is_acute_crisis: bool
    is_venting: bool

    @classmethod
    def evaluate(cls, text: str) -> "MSymPrevNode":
        t_lower = text.lower()
        # Quality of Life Engine distinction: venting vs composed command
        if any(w in t_lower for w in ["fuck this", "break everything", "hate this", "burn it"]):
            # High arousal, low valence, low dominance -> venting
            return cls(
                raw_utterance=text,
                valence=-0.75,
                arousal=0.92,
                dominance=0.35,
                is_acute_crisis=False,
                is_venting=True
            )
        elif "disregard" in t_lower or "deprecate" in t_lower or "cancel" in t_lower:
            # Composed instruction: neutral valence, low arousal, high dominance
            return cls(
                raw_utterance=text,
                valence=0.05,
                arousal=0.20,
                dominance=0.85,
                is_acute_crisis=False,
                is_venting=False
            )
        return cls(raw_utterance=text, valence=0.2, arousal=0.3, dominance=0.5, is_acute_crisis=False, is_venting=False)

@dataclass
class SSymPrevNode:
    """Simulation SymLink Preview - Golden synthetic rollouts feeding DSymPrev."""
    scenario_id: str
    golden_trajectory: Dict[str, Any]
    confidence_score: float  # [0.0000, 1.0000]
    passed_stress_test: bool
    promoted_to_dsymprev: bool = False
