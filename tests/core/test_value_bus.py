import threading
import time
import unittest

from loci_engine.value_bus import Bus, SlotState, ValueBus, ValueBusError, route, watch_stream


class ValueBusTests(unittest.TestCase):
    def test_tentative_values_are_never_forwarded(self):
        bus = ValueBus()
        bus.declare("total", int)
        bus.propose("total", 42, confidence=0.5)
        self.assertIsNone(bus.get("total"))
        self.assertEqual(bus.state("total"), SlotState.TENTATIVE)
        bus.propose("total", 47, confidence=0.5)  # producer revised itself
        bus.commit("total")
        self.assertEqual(bus.get("total"), 47)

    def test_high_confidence_auto_commits(self):
        bus = ValueBus(auto_commit_confidence=0.9)
        self.assertEqual(bus.propose("x", 3, confidence=0.95), SlotState.COMMITTED)

    def test_committed_value_is_immutable(self):
        bus = ValueBus()
        bus.commit("port", 8765)
        bus.commit("port", 8765)  # idempotent
        with self.assertRaises(ValueBusError):
            bus.commit("port", 8000)
        with self.assertRaises(ValueBusError):
            bus.propose("port", 1)

    def test_type_checked(self):
        bus = ValueBus()
        bus.declare("n", int)
        bus.commit("n", "12")
        self.assertEqual(bus.get("n"), 12)
        bus.declare("m", int)
        with self.assertRaises(ValueBusError):
            bus.commit("m", "not a number")

    def test_wait_blocks_only_until_commit(self):
        bus = ValueBus()
        got = {}

        def consumer():
            got["v"] = bus.wait("answer", timeout=5)

        t = threading.Thread(target=consumer)
        t.start()
        time.sleep(0.05)
        bus.propose("answer", 41, confidence=0.5)
        time.sleep(0.05)
        self.assertNotIn("v", got)  # still stalled on a tentative value
        bus.commit("answer", 42)
        t.join(2)
        self.assertEqual(got["v"], 42)

    def test_wait_timeout(self):
        with self.assertRaises(TimeoutError):
            ValueBus().wait("never", timeout=0.05)

    def test_watch_stream_early_forwarding(self):
        bus = ValueBus()
        watch_stream(bus, "Working: total = 4,100 so far.", keys=["total"])
        self.assertIsNone(bus.get("total"))
        watch_stream(bus, "Final answer: total = 4,217.", keys=["total"])
        self.assertEqual(bus.get("total"), 4217)
        self.assertIn("total", bus.snapshot())

    def test_router_defaults_to_value_bus(self):
        self.assertEqual(route("how many invoices were paid"), Bus.VALUE)
        self.assertEqual(route("explain the background of the project"), Bus.HEAT)
        self.assertEqual(route("something vague"), Bus.VALUE)
        self.assertEqual(route("explain the total", classifier=lambda _: Bus.HEAT), Bus.HEAT)


if __name__ == "__main__":
    unittest.main()
