import unittest
from loci_engine.loop_guard import LoopGuardCircuitBreaker

class TestLoopGuard(unittest.TestCase):
    def setUp(self):
        self.guard = LoopGuardCircuitBreaker(threshold=3)

    def test_progressive_execution_allowed(self):
        # Progressing operations with mutating parameters
        res1 = self.guard.record_and_evaluate("query", {"offset": 0})
        res2 = self.guard.record_and_evaluate("query", {"offset": 10})
        self.assertFalse(res1["circuit_tripped"])
        self.assertFalse(res2["circuit_tripped"])
        self.assertEqual(res2["action"], "CONTINUE")

    def test_deterministic_n3_loop_abort(self):
        # 3 consecutive identical actions trigger the circuit breaker
        action = "fetch_tool_output"
        params = {"tool": "cat", "target": "missing.log"}

        r1 = self.guard.record_and_evaluate(action, params)
        self.assertFalse(r1["circuit_tripped"])
        self.assertEqual(r1["consecutive_count"], 1)

        r2 = self.guard.record_and_evaluate(action, params)
        self.assertFalse(r2["circuit_tripped"])
        self.assertEqual(r2["consecutive_count"], 2)

        r3 = self.guard.record_and_evaluate(action, params)
        self.assertTrue(r3["circuit_tripped"])
        self.assertEqual(r3["consecutive_count"], 3)
        self.assertEqual(r3["action"], "DETERMINISTIC_ABORT")

if __name__ == "__main__":
    unittest.main()
