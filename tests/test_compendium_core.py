import unittest
from loci_engine.dream_engine import GeodesicDreamEngine
from loci_engine.slp_arena import SymLinkPrevNode, CacheLineSlot64B

class TestCompendiumCore(unittest.TestCase):
    def test_geodesic_dream_score(self):
        # Two high-heat, distant concepts (Orthogonal vectors: dist = 1.0)
        node_a = {"id": "thermo_physics", "heat": 0.95, "embedding": [1.0, 0.0, 0.0]}
        node_b = {"id": "neural_memory", "heat": 0.90, "embedding": [0.0, 1.0, 0.0]}
        
        res = GeodesicDreamEngine.evaluate_dream_pair(node_a, node_b)
        self.assertTrue(res["is_viable"])
        self.assertAlmostEqual(res["geodesic_distance"], 1.0, places=4)
        # Score = 1.0 * 0.95 * 0.90 = 0.855
        self.assertAlmostEqual(res["dream_score"], 0.855, places=3)
        self.assertEqual(res["stream_quarantine"], "DSymPrev")
        self.assertEqual(res["epistemic_confidence"], 0.0)

    def test_slp_20byte_node_packing(self):
        packed = SymLinkPrevNode.pack(b"node_001", b"DOM1", 0.85, 0.92, 1042)
        self.assertEqual(len(packed), 20)  # Must be exactly 20 bytes
        
        unpacked = SymLinkPrevNode.unpack(packed)
        self.assertEqual(unpacked["domain_id"], "DOM1")
        self.assertAlmostEqual(unpacked["heat"], 0.85, places=2)
        self.assertAlmostEqual(unpacked["trust"], 0.92, places=2)
        self.assertEqual(unpacked["lineage_id"], 1042)

    def test_cache_line_64byte_alignment(self):
        n1 = SymLinkPrevNode.pack(b"node_001", b"DOM1", 0.9, 0.9, 1)
        n2 = SymLinkPrevNode.pack(b"node_002", b"DOM1", 0.8, 0.8, 2)
        n3 = SymLinkPrevNode.pack(b"node_003", b"DOM2", 0.7, 0.7, 3)
        
        slot = CacheLineSlot64B.pack_slot(slot_flags=0x01, nodes=[n1, n2, n3])
        self.assertEqual(len(slot), 64)  # Must fit exactly one CPU cache line

if __name__ == "__main__":
    unittest.main()
