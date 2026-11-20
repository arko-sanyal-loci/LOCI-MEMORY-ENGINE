"""route_inference() must exist and choose lanes in the documented order."""
import unittest
from unittest import mock

from loci_engine import gpu_governor as gg


def _nv(ok=True, margin=True, headroom=10_000):
    return {"can_accept_task": ok, "within_safety_margin": margin, "vram_headroom_mb": headroom}


def _arc(ready=True, ok=True):
    return {"compute_ready": ready, "can_accept_task": ok}


class RouteInferenceTest(unittest.TestCase):
    def route(self, nv, arc, **kw):
        with mock.patch.object(gg, "get_nvidia_status", return_value=nv), \
             mock.patch.object(gg, "get_intel_arc_status", return_value=arc):
            return gg.route_inference("m", **kw)

    def test_prefers_nvidia_with_headroom(self):
        self.assertEqual(self.route(_nv(), _arc())["gpu"], "nvidia_rtx_5060_ti")

    def test_big_model_goes_to_arc(self):
        r = self.route(_nv(headroom=4_000), _arc(), vram_estimate_mb=20_000)
        self.assertEqual(r["gpu"], "intel_arc_b580_pro")
        self.assertEqual(r["endpoint"], gg.OLLAMA_ENDPOINTS["intel_arc_b580_pro"])

    def test_falls_back_to_nvidia_when_arc_not_ready(self):
        r = self.route(_nv(margin=False), _arc(ready=False))
        self.assertEqual(r["gpu"], "nvidia_rtx_5060_ti")

    def test_queues_when_both_full(self):
        r = self.route(_nv(ok=False), _arc(ok=False))
        self.assertTrue(r["queue"])
        self.assertIsNone(r["endpoint"])


if __name__ == "__main__":
    unittest.main()
