#!/usr/bin/env python3
"""
Loci Memory Engine - Deterministic Loop Guard Circuit Breaker
Implements Compendium Section 1 & Figure 1A:
Sliding ring buffer tracking composite state hashes, triggering abort at N=3 duplicate states.
"""

import hashlib
import json
from typing import List, Dict, Any

class LoopGuardCircuitBreaker:
    DEFAULT_THRESHOLD_N = 3

    def __init__(self, threshold: int = DEFAULT_THRESHOLD_N):
        self.threshold = threshold
        self.state_history: List[str] = []

    def compute_state_hash(self, action: str, params: Dict[str, Any]) -> str:
        serialized = json.dumps(params, sort_keys=True, separators=(',', ':'))
        payload = f"{action}:{serialized}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def record_and_evaluate(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        state_hash = self.compute_state_hash(action, params)
        self.state_history.append(state_hash)

        # Count consecutive identical state hashes at the tail
        consecutive_count = 0
        for h in reversed(self.state_history):
            if h == state_hash:
                consecutive_count += 1
            else:
                break

        circuit_tripped = consecutive_count >= self.threshold

        return {
            "state_hash": state_hash,
            "consecutive_count": consecutive_count,
            "threshold": self.threshold,
            "circuit_tripped": circuit_tripped,
            "action": "DETERMINISTIC_ABORT" if circuit_tripped else "CONTINUE"
        }

    def reset(self):
        self.state_history.clear()
