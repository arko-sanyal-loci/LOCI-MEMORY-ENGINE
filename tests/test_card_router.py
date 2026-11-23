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

    def test_stream_and_tiebreaker_resolve_close_candidates(self):
        candidates = [
            {"id": "cold", "heat": 0.70, "timestamp": 1},
            {"id": "stream", "heat": 0.68, "timestamp": 2},
            {"id": "hot", "heat": 0.50, "timestamp": 3},
        ]
        res = CardRouter.execute_card_retrieval(
            "What is the deployment plan?",
            candidates,
            stream_context=[{"id": "stream", "score": 1.0, "hop": 1}],
            tiebreaker_context={"stream": 1.0, "cold": -1.0},
        )
        self.assertEqual(res["selected_items"][0]["id"], "stream")
        self.assertEqual(res["selected_items"][-1]["id"], "hot")
        self.assertEqual(res["selected_items"][0]["stream_score"], 0.5)

    def test_context_cannot_override_material_heat_difference(self):
        candidates = [
            {"id": "hot", "heat": 0.90},
            {"id": "cold", "heat": 0.70},
        ]
        res = CardRouter.execute_card_retrieval(
            "What is the deployment plan?",
            candidates,
            stream_context=[{"id": "cold", "score": 1.0, "hop": 1}],
            tiebreaker_context={"cold": 1.0},
        )
        self.assertEqual(res["selected_items"][0]["id"], "hot")

    def test_context_scores_are_capped_and_category_hint_is_validated(self):
        candidates = [
            {"id": "a", "heat": 0.60},
            {"id": "b", "heat": 0.60},
        ]
        res = CardRouter.execute_card_retrieval(
            "What is the answer?",
            candidates,
            category_hint="information_extraction",
            stream_context=[
                {"id": "a", "score": 99, "hop": 1},
                {"id": "a", "score": 1, "hop": 2},
            ],
            tiebreaker_context={"a": 99},
        )
        self.assertEqual(res["archetype"], "information_extraction")
        selected = next(item for item in res["selected_items"] if item["id"] == "a")
        self.assertEqual(selected["stream_score"], 0.5)
        self.assertEqual(selected["tiebreaker_score"], 1.0)

        invalid = CardRouter.execute_card_retrieval(
            "What is the answer?",
            candidates,
            category_hint="not_a_real_archetype",
        )
        self.assertEqual(invalid["archetype"], "information_extraction")

if __name__ == "__main__":
    unittest.main()
