#!/usr/bin/env python3
"""Audit trace and SYMPREV review. Synthetic text only."""

import json
import os
import tempfile
import unittest
from datetime import datetime

from loci_engine.audit_trace import LIMITATION, AuditTrace, verify_chain
from loci_engine.card_router import CardRouter
from loci_engine.learning_cycle import LearningCycle, TaskRequest
from loci_engine.symprev_review import ALIASES, estimate_tokens, measure_context, reexpand, review_context


REQUIRED_STEPS = [
    "retrieval",
    "heat_scoring",
    "paper_indexing",
    "category_selection",
    "research",
    "execution",
    "dream_batch",
    "review_compression",
    "reflection_persistence",
]


class AuditTests(unittest.TestCase):
    def setUp(self):
        handle = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
        handle.close()
        os.unlink(handle.name)
        self.path = handle.name
        self.db = self.path + ".db"

    def tearDown(self):
        for path in (self.path, self.db, self.db + "-wal", self.db + "-shm"):
            if os.path.exists(path):
                os.unlink(path)

    def test_steps_are_ordered_timestamped_and_not_a_clock_proof(self):
        trace = AuditTrace(self.path, config={"heat_scale": "routine_observation"}, code_version="test")
        cycle = LearningCycle(self.db, trace=trace)
        cycle.run(
            TaskRequest(
                task_key="mixweight",
                objective="Choose a mixing weight offline.",
                options=["w02", "w05", "w08"],
                query="mixweight option",
                dream_scores={"w02": 0.2, "w05": 0.5, "w08": 0.8},
            )
        )
        rows = trace.records()
        self.assertEqual(rows[0]["kind"], "header")
        self.assertIn("do not prove wall-clock", rows[0]["limitation"])
        self.assertIsNone(rows[0]["attestation"])
        steps = [row for row in rows if row["kind"] == "step"]
        self.assertEqual([row["name"] for row in steps], REQUIRED_STEPS)
        self.assertEqual(steps[2]["status"], "skipped")
        self.assertEqual(steps[2]["name"], "paper_indexing")
        previous_end = None
        for row in steps:
            start = datetime.fromisoformat(row["wall_start"])
            end = datetime.fromisoformat(row["wall_end"])
            self.assertIsNotNone(start.tzinfo)
            self.assertIsNotNone(end.tzinfo)
            self.assertGreaterEqual(end, start)
            self.assertGreaterEqual(row["monotonic_duration_seconds"], 0.0)
            self.assertTrue(row["step_id"].startswith(trace.run_id))
            self.assertEqual(row["code_version"], "test")
            if previous_end is not None:
                self.assertGreaterEqual(start, previous_end)
            previous_end = end
        checked = verify_chain(self.path)
        self.assertTrue(checked["ok"])
        self.assertFalse(checked["proves_wall_clock"])
        self.assertFalse(checked["proves_live_observation"])
        self.assertEqual(checked["limitation"], LIMITATION)

    def test_errors_are_recorded_and_a_tampered_line_fails_the_chain(self):
        trace = AuditTrace(self.path, code_version="test")
        with self.assertRaises(RuntimeError):
            with trace.step("boom", {"safe": True}):
                raise RuntimeError("stopped")
        steps = [row for row in trace.records() if row["kind"] == "step"]
        self.assertEqual(steps[-1]["status"], "error")
        self.assertEqual(steps[-1]["error_type"], "RuntimeError")
        self.assertNotEqual(steps[-1]["status"], "completed")
        self.assertTrue(verify_chain(self.path)["ok"])
        with open(self.path, encoding="utf-8") as handle:
            raw = handle.read().splitlines()
        broken = raw[:-1] + [raw[-1].replace("error", "completed", 1)]
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(broken) + "\n")
        self.assertFalse(verify_chain(self.path)["ok"])


class SymprevTests(unittest.TestCase):
    def test_alias_map_does_not_invent_simlink(self):
        self.assertIn("SYMPREV", ALIASES)
        self.assertIn("QSymPrev", ALIASES)
        self.assertIn("DSymPrev", ALIASES)
        self.assertIn("SymLinkPrev", ALIASES)
        self.assertIn("not a module", ALIASES["SimLink"])

    def test_exact_fact_survives_a_budget_that_cannot_hold_prose(self):
        facts = [{
            "source_id": "m1",
            "quantity": 0.55,
            "unit": "loss",
            "polarity": "negative",
        }]
        prose = "background " * 80
        packet = review_context(
            query="what mixing weight is stored",
            items=[{
                "id": "blob",
                "statement": prose,
                "heat": 0.9,
                "support": True,
                "source_id": "blob",
            }],
            exact_facts=facts,
            policy={"allow_execution": False, "hard_constraints": ["explicit_consent_required"], "v_exec": 0.7},
            token_budget=8,
        )
        self.assertFalse(packet["called_golden"])
        self.assertFalse(packet["exact_facts_truncated"])
        self.assertEqual(packet["exact_facts"], facts)
        self.assertEqual(packet["policy"]["allow_execution"], False)
        self.assertEqual(packet["status"], "budget_exceeded_exact_facts_retained")
        self.assertEqual(packet["symbols"], [])
        self.assertEqual(packet["token_estimate_method"], "utf8_bytes_div_4")
        again = reexpand(packet, "blob", {"blob": prose})
        self.assertEqual(again["status"], "reexpanded")
        self.assertEqual(again["text"], prose)
        missing = reexpand(packet, "absent", {})
        self.assertEqual(missing["status"], "missing_support")
        self.assertTrue(missing["abstained"])

    def test_category_budget_duplicates_and_contradictions(self):
        info = CardRouter.ARCHETYPE_CONFIGS["information_extraction"]["max_tokens"]
        multi = CardRouter.ARCHETYPE_CONFIGS["multi_session_reasoning"]["max_tokens"]
        self.assertEqual(info, 180)
        self.assertEqual(multi, 450)
        same = "same lesson text"
        packet = review_context(
            query="what is stored",
            items=[
                {"id": "a", "statement": same, "heat": 0.9, "support": True, "source_id": "a"},
                {"id": "b", "statement": same, "heat": 0.9, "support": True, "source_id": "b"},
                {"id": "c", "statement": "other lesson", "heat": 0.9, "support": True, "contradictory": True, "source_id": "c"},
                {"id": "d", "statement": "unsupported lesson", "heat": 0.9, "support": False, "source_id": "d"},
            ],
            exact_facts=[],
            policy={"allow_execution": True, "hard_constraints": [], "v_exec": 0.4},
        )
        self.assertEqual(packet["token_budget"], 180)
        self.assertEqual([row["id"] for row in packet["symbols"]], ["a"])
        reasons = {row["id"]: row["reason"] for row in packet["dropped"]}
        self.assertEqual(reasons["b"], "redundant")
        self.assertEqual(reasons["c"], "contradictory")
        self.assertEqual(reasons["d"], "unsupported")
        measured = measure_context(same * 20, packet)
        self.assertFalse(measured["model_invoked"])
        self.assertIsNone(measured["money_saved"])
        self.assertFalse(measured["quality_guaranteed"])
        self.assertLess(measured["selected"]["tokens"], measured["baseline"]["tokens"])
        self.assertGreater(measured["review_overhead"]["tokens"], 0)
        self.assertEqual(estimate_tokens("abcd")["method"], "utf8_bytes_div_4")


if __name__ == "__main__":
    unittest.main()
