import unittest

from loci_engine import tau_gate as tg


PEAKED = [0.95, 0.60, 0.58, 0.57, 0.55, 0.54, 0.52, 0.50, 0.49, 0.48]
FLAT = [0.51, 0.50, 0.50, 0.50, 0.49, 0.49, 0.49, 0.49, 0.48, 0.48]


class ShapeTests(unittest.TestCase):
    def test_too_few_scores_always_escalates(self):
        self.assertEqual(tg.shape_tau([0.9, 0.1]), 999.0)

    def test_flat_raises_and_peaked_lowers(self):
        self.assertGreater(tg.shape_tau(FLAT), tg.BASE_TAU)
        self.assertLess(tg.shape_tau(PEAKED), tg.BASE_TAU)

    def test_order_does_not_matter(self):
        self.assertAlmostEqual(tg.shape_tau(list(reversed(PEAKED))), tg.shape_tau(PEAKED))


class ConfidenceTests(unittest.TestCase):
    def test_option2_formula_exactly_as_specified(self):
        self.assertAlmostEqual(tg.confidence_tau([1.0]), 1.75)
        self.assertAlmostEqual(tg.confidence_tau([0.0]), 3.5)

    def test_tracker_learns(self):
        t = tg.ConfidenceTracker()
        for _ in range(30):
            t.record("port", True)
        self.assertGreater(t.get("port"), 0.9)
        self.assertEqual(t.get("unknown"), 0.5)

    def test_multiplier_worked_example(self):
        self.assertAlmostEqual(tg.confidence_multiplier([0.875]), 0.70)


class QueryTypeTests(unittest.TestCase):
    def test_classifier(self):
        self.assertEqual(tg.classify_query_type("what port does the broker use"), "lookup")
        self.assertEqual(tg.classify_query_type("broker"), "ambiguous")
        self.assertEqual(tg.classify_query_type("who is the CEO of the company"), "adversarial")
        self.assertEqual(tg.classify_query_type("describe the decay engine design"), "descriptive")


class DynamicTauTests(unittest.TestCase):
    def test_peaked_lookup_in_hot_era_passes(self):
        d = tg.dynamic_tau("what port does the broker use", PEAKED,
                           hit_eras=["s1"] * 10, era_heat={"s1": 0.9}, confidences=[0.9] * 5)
        self.assertTrue(d.passed, d)
        self.assertEqual(d.era_temperature, "hot")

    def test_no_temporal_anchor_is_out_of_context(self):
        d = tg.dynamic_tau("who is the ceo of acme", FLAT, hit_eras=[None] * 10)
        self.assertEqual(d.tau, tg.TAU_OOC)
        self.assertFalse(d.passed)

    def test_flat_distribution_fails(self):
        self.assertFalse(tg.dynamic_tau("describe the decay engine design", FLAT).passed)

    def test_few_hits_escalate(self):
        self.assertFalse(tg.dynamic_tau("what port", [0.9, 0.2]).passed)


class MrrTests(unittest.TestCase):
    def test_reciprocal_rank_and_abstention(self):
        self.assertEqual(tg.reciprocal_rank(["a", "b"], ["b"]), 0.5)
        self.assertEqual(tg.reciprocal_rank([], []), 1.0)
        self.assertEqual(tg.reciprocal_rank(["x"], []), 0.0)

    def test_targets(self):
        fast = [(["a"], ["a"]), (["b", "a"], ["a"]), ([], [])]
        full = [(["a"], ["a"]), (["a"], ["a"])]
        r = tg.evaluate_mrr(fast, full)
        self.assertAlmostEqual(r["slp_mrr"], 0.75)
        self.assertAlmostEqual(r["slp_over_full"], 0.75)
        self.assertEqual(r["meets"], {"slp_over_full": False, "absolute": True, "adversarial": True})


if __name__ == "__main__":
    unittest.main()
