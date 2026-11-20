"""HOT threshold is a single constant at 0.70 and every consumer uses it."""
import unittest

from loci_engine import heat
from loci_engine.thermal_gradient import ThermodynamicNeighborhoodEngine as TNE


class HotThresholdTests(unittest.TestCase):
    def test_single_hot_boundary_at_070(self):
        self.assertEqual(heat.TIER_HOT_BOUNDARY, 0.70)
        self.assertEqual(heat.VRAM_ADMISSION_THRESHOLD, heat.TIER_HOT_BOUNDARY)

    def test_tier_edges(self):
        self.assertEqual(heat.tier(0.70), "hot")
        self.assertEqual(heat.tier(0.6999), "mild")
        self.assertEqual(heat.tier(0.35), "mild")
        self.assertEqual(heat.tier(0.3499), "cold")

    def test_user_turn_default_heat_is_hot(self):
        # session_ingester stores user turns at 0.75; at the old 0.80 boundary
        # every fresh user turn was MILD, i.e. never in the VRAM working set.
        self.assertEqual(heat.tier(0.75), "hot")

    def test_thermal_gradient_uses_heat_module(self):
        self.assertEqual(TNE.TIER_HOT_THRESHOLD, heat.TIER_HOT_BOUNDARY)
        self.assertEqual(TNE.TIER_MILD_THRESHOLD, heat.TIER_MILD_BOUNDARY)
        self.assertEqual(TNE.classify_tier(0.71), "HOT")

    def test_reinforce_stays_in_open_interval(self):
        h = heat.ALPHA_FLOOR
        for _ in range(200):
            h = heat.reinforce(h)
        self.assertLess(h, 1.0)
        self.assertLessEqual(h, heat.HEAT_CEILING)
        self.assertGreater(heat.reinforce(0.333), 0.333)
        self.assertAlmostEqual(heat.reinforce(0.4, hop=1), 0.4 + 0.6 * 0.25)
        self.assertEqual(heat.reinforce(0.4, hop=9), 0.4)

    def test_tier_tau(self):
        self.assertEqual(heat.tier_tau(0.9), heat.TIER_TAU["hot"])
        self.assertEqual(heat.tier_tau(0.1), heat.TIER_TAU["cold"])


if __name__ == "__main__":
    unittest.main()
