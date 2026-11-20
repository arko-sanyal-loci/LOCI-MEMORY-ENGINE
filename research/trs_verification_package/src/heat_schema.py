"""
LOCI Thermal Naming Schema & Granular Heat Engine
Reconciled for the Ptyxis Collective & LOCI Substrate.

Canonical Tiers:
- HOT:  H >= 0.8000 (VRAM Active Working Set, tau = 1.25)
- MILD: 0.3500 <= H < 0.8000 (Host RAM SymLinkPrev Arena, tau = 1.75)
- COLD: 0.0500 <= H < 0.3500 (NVMe Archival Ledger, tau = 2.25)
Floor:  alpha = 0.0500 (The Constant of Hope - memory never fully reaches zero)
Ceiling: H < 1.0000 (Open-interval proof - trauma never reaches 100%)
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Dict, List, Tuple

class ThermalTier(str, Enum):
    HOT = "HOT"
    MILD = "MILD"
    COLD = "COLD"

ALPHA_FLOOR = 0.0500
MAX_CEILING = 0.9999
UINT16_MAX = 65535

def quantize_heat(heat_float: float) -> int:
    """Pack continuous float into 16-bit uint for SymLinkPrev RAM arena (Bytes 0x0C-0x0D)."""
    clamped = max(ALPHA_FLOOR, min(MAX_CEILING, heat_float))
    normalized = (clamped - ALPHA_FLOOR) / (MAX_CEILING - ALPHA_FLOOR)
    return int(round(normalized * UINT16_MAX))

def dequantize_heat(raw_uint16: int) -> float:
    """Unpack 16-bit uint back to high-precision float (step size ~ 0.0000145)."""
    raw_uint16 = max(0, min(UINT16_MAX, raw_uint16))
    normalized = raw_uint16 / UINT16_MAX
    val = ALPHA_FLOOR + normalized * (MAX_CEILING - ALPHA_FLOOR)
    return round(val, 4)

def classify_tier(heat: float) -> Tuple[ThermalTier, float]:
    """Classify heat into modular tiers with associated confidence threshold tau."""
    if heat >= 0.8000:
        return ThermalTier.HOT, 1.25
    elif heat >= 0.3500:
        return ThermalTier.MILD, 1.75
    else:
        return ThermalTier.COLD, 2.25

@dataclass
class SemanticNode:
    entity: str
    relevance_score: float  # 4-decimal precision r_j in [0.0000, 1.0000]
    base_heat: float        # Current accumulated heat
    tier: ThermalTier
    tau_threshold: float

class ThermalGraph:
    def __init__(self, beta: float = 0.85):
        self.beta = beta
        self.nodes: Dict[str, SemanticNode] = {}
        self.edges: Dict[str, List[Tuple[str, float]]] = {}  # neighbor, weight

    def add_node(self, entity: str, initial_heat: float = ALPHA_FLOOR):
        tier, tau = classify_tier(initial_heat)
        self.nodes[entity] = SemanticNode(
            entity=entity,
            relevance_score=0.0000,
            base_heat=initial_heat,
            tier=tier,
            tau_threshold=tau
        )
        if entity not in self.edges:
            self.edges[entity] = []

    def add_edge(self, source: str, target: str, weight: float = 1.0):
        if source not in self.edges:
            self.edges[source] = []
        self.edges[source].append((target, weight))

    def activate_semantic_cue(self, target_entity: str, r_j: float, max_hops: int = 2) -> Dict[str, Dict]:
        """
        Hybrid Activation:
        - Modular integer hops: 0 (direct), 1 (immediate), 2 (extended)
        - Granular scaling: Delta H = r_j * (0.5)^hop * edge_weight
        """
        r_j = round(max(0.0, min(1.0, r_j)), 4)
        updates = {}
        visited = set()
        queue = [(target_entity, 0, 1.0)]  # entity, hop, path_weight

        while queue:
            current, hop, path_weight = queue.pop(0)
            if current in visited or hop > max_hops:
                continue
            visited.add(current)

            hop_decay = (0.5) ** hop
            delta_heat = round(r_j * hop_decay * path_weight, 4)

            node = self.nodes.get(current)
            if node:
                # Saturation formula: H_new = H_old + (1 - H_old) * (1 - e^(-beta * delta_heat))
                old_h = node.base_heat
                gain = (1.0 - old_h) * (1.0 - math.exp(-self.beta * delta_heat))
                new_h = round(min(MAX_CEILING, old_h + gain), 4)
                
                # Check quantization fidelity
                packed = quantize_heat(new_h)
                unpacked = dequantize_heat(packed)

                tier, tau = classify_tier(unpacked)
                node.base_heat = unpacked
                node.relevance_score = r_j if hop == 0 else round(r_j * hop_decay, 4)
                node.tier = tier
                node.tau_threshold = tau

                updates[current] = {
                    "hop": hop,
                    "delta_heat": delta_heat,
                    "new_heat": unpacked,
                    "packed_uint16": packed,
                    "tier": tier.value,
                    "tau": tau
                }

            if hop < max_hops and current in self.edges:
                for neighbor, weight in self.edges[current]:
                    if neighbor not in visited:
                        queue.append((neighbor, hop + 1, path_weight * weight))

        return updates
