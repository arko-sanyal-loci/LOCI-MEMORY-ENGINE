import unittest
from loci_engine.simulation_engine import CounterfactualSimulationEngine

class TestSimulationEngine(unittest.TestCase):
    def test_behavioral_surprise_metric(self):
        pred = {"latency": 0.10, "tokens": 0.20, "err": 0.0}
        actual = {"latency": 0.60, "tokens": 0.20, "err": 0.0}
        # Surprise = sqrt((0.5)^2) = 0.50
        surprise = CounterfactualSimulationEngine.evaluate_behavioral_surprise(pred, actual)
        self.assertAlmostEqual(surprise, 0.50, places=4)

    def test_what_if_neighborhood_curiosity(self):
        curr = {"id": "current_plan", "heat": 0.8, "embedding": [1.0, 0.0, 0.0]}
        neighbors = [
            {"id": "alt_heuristic_a", "embedding": [0.95, 0.05, 0.0]},
            {"id": "alt_heuristic_b", "embedding": [0.10, 0.90, 0.0]}
        ]
        
        sims = CounterfactualSimulationEngine.generate_what_if_probe(
            current_context_node=curr,
            neighbor_nodes=neighbors,
            delta_surprise=0.45
        )
        
        # Closely aligned alternative should receive highest reflective heat (H_sim)
        self.assertEqual(sims[0]["counterfactual_target_id"], "alt_heuristic_a")
        self.assertEqual(sims[0]["stream_quarantine"], "DSimPrev")
        self.assertEqual(sims[0]["epistemic_confidence"], 0.0)
        self.assertTrue(sims[0]["valence_clearance"])

if __name__ == "__main__":
    unittest.main()
