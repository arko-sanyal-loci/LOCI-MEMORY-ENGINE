import unittest
from loci_engine.card_router import CardRouter

class TestCardRouter(unittest.TestCase):
    def setUp(self):
        self.candidates = [
            {"id": "c1", "entity_id": "vps_ip", "heat": 0.8, "timestamp": 100, "embedding": [1.0, 0.0]},
            {"id": "c2", "entity_id": "vps_ip", "heat": 0.8, "timestamp": 200, "embedding": [0.95, 0.05]},
            {"id": "c3", "entity_id": "dns_rec", "heat": 0.3, "timestamp": 150, "embedding": [0.85, 0.15]},
        ]

    def test_knowledge_update_deduplication(self):
        res = CardRouter.execute_card_retrieval("What is the latest updated vps_ip?", self.candidates)
        self.assertEqual(res["archetype"], "knowledge_update")
        self.assertEqual(res["depth_k"], 3)
        # Should pick timestamp 200 over 100
        self.assertEqual(res["selected_items"][0]["id"], "c2")

    def test_temporal_ordering(self):
        res = CardRouter.execute_card_retrieval("What was the history of changes before today?", self.candidates)
        self.assertEqual(res["archetype"], "temporal_reasoning")
        self.assertEqual(res["depth_k"], 7)
        # Chronological order
        timestamps = [item["timestamp"] for item in res["selected_items"]]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_gradient_conduction(self):
        res = CardRouter.execute_card_retrieval(
            "Synthesize why dns_rec relates to vps",
            self.candidates,
            active_embedding=[1.0, 0.0]
        )
        self.assertEqual(res["archetype"], "multi_session_reasoning")
        # c3 should absorb conducted heat from active embedding
        c3 = next(x for x in res["selected_items"] if x["id"] == "c3")
        self.assertGreater(c3["effective_heat"], 0.3)

if __name__ == "__main__":
    unittest.main()
