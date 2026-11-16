"""
tests/test_paper08_facts.py
============================
Paper 08 (Persistent Memory Engine) — fact versioning test suite.
"""
import json
import os
import tempfile
import time
import unittest
from datetime import datetime, timezone

from loci_engine.storage import StorageEngine, _TRUST_FLOOR, _TRUST_DOMINANT


class TestPaper08FactVersioning(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.tmp.close()
        self.db = StorageEngine(db_path=self.tmp.name)

    def tearDown(self):
        os.unlink(self.tmp.name)

    def _value(self, fact: dict) -> str:
        return json.loads(fact["structured_value"])["value"]

    def test_insert_new_fact(self):
        result = self.db.upsert_fact("server", "port", "8080")
        self.assertTrue(result["accepted"])
        self.assertEqual(result["action"], "inserted")
        fact = self.db.get_current_fact("server", "port")
        self.assertIsNotNone(fact)
        self.assertEqual(self._value(fact), "8080")
        self.assertEqual(fact["status"], "active")

    def test_insert_stores_entity_key_value(self):
        self.db.upsert_fact("server", "host", "localhost", source_trust=0.9)
        fact = self.db.get_current_fact("server", "host")
        sv = json.loads(fact["structured_value"])
        self.assertEqual(sv["entity_id"], "server")
        self.assertEqual(sv["key"], "host")
        self.assertEqual(sv["value"], "localhost")

    def test_update_fact_same_trust(self):
        self.db.upsert_fact("server", "port", "8080", source_trust=0.9)
        result = self.db.upsert_fact("server", "port", "9090", source_trust=0.9)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["action"], "superseded")
        self.assertEqual(self._value(self.db.get_current_fact("server", "port")), "9090")
        self.assertFalse(result["dominant"])

    def test_superseded_old_fact_has_valid_until(self):
        self.db.upsert_fact("server", "port", "8080", source_trust=0.9)
        self.db.upsert_fact("server", "port", "9090", source_trust=0.9)
        history = self.db.get_fact_history("server", "port")
        self.assertEqual(len(history), 2)
        active = next(h for h in history if h["status"] == "active")
        superseded = next(h for h in history if h["status"] == "superseded")
        self.assertIsNotNone(superseded["valid_until"])
        self.assertIsNone(active["valid_until"])

    def test_trust_floor_rejects_low_trust(self):
        self.db.upsert_fact("server", "port", "8080", source_trust=0.95)
        result = self.db.upsert_fact("server", "port", "9090", source_trust=0.5)
        self.assertFalse(result["accepted"])
        self.assertEqual(result["action"], "rejected")
        self.assertEqual(result["reason"], "trust_below_floor")
        self.assertLess(result["trust_ratio"], _TRUST_FLOOR)
        self.assertEqual(self._value(self.db.get_current_fact("server", "port")), "8080")

    def test_trust_floor_exact_boundary_accepted(self):
        self.db.upsert_fact("server", "port", "8080", source_trust=1.0)
        result = self.db.upsert_fact("server", "port", "9090", source_trust=0.8)
        self.assertTrue(result["accepted"])

    def test_dominant_supersession(self):
        self.db.upsert_fact("server", "host", "old-host", source_trust=0.5)
        result = self.db.upsert_fact("server", "host", "new-host", source_trust=0.9)
        self.assertTrue(result["accepted"])
        self.assertTrue(result["dominant"])

    def test_non_dominant_flag(self):
        self.db.upsert_fact("server", "port", "8080", source_trust=0.9)
        result = self.db.upsert_fact("server", "port", "9090", source_trust=0.95)
        self.assertTrue(result["accepted"])
        self.assertFalse(result["dominant"])

    def test_get_fact_at_returns_historic_value(self):
        self.db.upsert_fact("server", "port", "8080", source_trust=0.9)
        checkpoint = datetime.now(timezone.utc).isoformat()
        time.sleep(0.05)
        self.db.upsert_fact("server", "port", "9090", source_trust=0.9)
        fact_at = self.db.get_fact_at("server", "port", checkpoint)
        self.assertIsNotNone(fact_at)
        self.assertEqual(self._value(fact_at), "8080")
        self.assertEqual(self._value(self.db.get_current_fact("server", "port")), "9090")

    def test_get_fact_at_before_creation_returns_none(self):
        past = "2000-01-01T00:00:00+00:00"
        self.db.upsert_fact("server", "port", "8080")
        self.assertIsNone(self.db.get_fact_at("server", "port", past))

    def test_full_history_chain(self):
        self.db.upsert_fact("db", "url", "v1", source_trust=0.9)
        self.db.upsert_fact("db", "url", "v2", source_trust=0.9)
        self.db.upsert_fact("db", "url", "v3", source_trust=0.9)
        history = self.db.get_fact_history("db", "url")
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0]["status"], "active")
        self.assertEqual(self._value(history[0]), "v3")
        for h in history[1:]:
            self.assertEqual(h["status"], "superseded")

    def test_independent_keys_no_interference(self):
        self.db.upsert_fact("server", "port", "8080")
        self.db.upsert_fact("server", "host", "localhost")
        self.assertEqual(self._value(self.db.get_current_fact("server", "port")), "8080")
        self.assertEqual(self._value(self.db.get_current_fact("server", "host")), "localhost")

    def test_same_key_different_entities(self):
        self.db.upsert_fact("server-a", "port", "8080")
        self.db.upsert_fact("server-b", "port", "9090")
        self.assertEqual(self._value(self.db.get_current_fact("server-a", "port")), "8080")
        self.assertEqual(self._value(self.db.get_current_fact("server-b", "port")), "9090")

    def test_missing_fact_returns_none(self):
        self.assertIsNone(self.db.get_current_fact("nobody", "nothing"))

    def test_empty_history_for_unknown_fact(self):
        self.assertEqual(self.db.get_fact_history("nobody", "nothing"), [])


if __name__ == "__main__":
    unittest.main()
