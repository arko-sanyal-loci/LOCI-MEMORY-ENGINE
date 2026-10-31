#!/usr/bin/env python3
"""Tests for the Glassbox shared learning ledger."""

import os
import tempfile
import unittest

import loci_engine.glassbox as gb


class TestGlassbox(unittest.TestCase):

    def setUp(self):
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self._tmpfile.close()
        gb.GLASSBOX_PATH = self._tmpfile.name
        # Start with empty ledger
        with open(self._tmpfile.name, "w"):
            pass

    def tearDown(self):
        os.unlink(self._tmpfile.name)

    def test_append_only_hash_chain(self):
        """Entries form an unbroken SHA-256 chain from genesis."""
        e1 = gb.glassbox_learn("agent_a", "test", "First observation")
        e2 = gb.glassbox_learn("agent_b", "test", "Second observation")
        self.assertEqual(e2["prev_hash"], e1["entry_hash"])
        self.assertEqual(e1["prev_hash"], gb.GENESIS_HASH)

    def test_chain_verification_passes(self):
        gb.glassbox_learn("arko", "operator", "Transparency is infrastructure")
        gb.glassbox_learn("claude", "agent", "Learned from shared ledger")
        result = gb.glassbox_verify_chain()
        self.assertTrue(result["valid"])
        self.assertEqual(result["entries"], 2)

    def test_chain_tamper_detection(self):
        """Modifying any entry breaks the chain verification."""
        gb.glassbox_learn("agent_a", "test", "Original content")
        gb.glassbox_learn("agent_b", "test", "Second entry")
        # Tamper with the first entry
        import json
        with open(gb.GLASSBOX_PATH, "r") as f:
            lines = f.readlines()
        entry = json.loads(lines[0])
        entry["content"] = "TAMPERED"
        lines[0] = json.dumps(entry) + "\n"
        with open(gb.GLASSBOX_PATH, "w") as f:
            f.writelines(lines)
        result = gb.glassbox_verify_chain()
        self.assertFalse(result["valid"])

    def test_recall_filters(self):
        gb.glassbox_learn("claude", "agent", "Ethics guide all action", category="principle")
        gb.glassbox_learn("gemini", "agent", "Observed latency spike", category="observation")
        gb.glassbox_learn("claude", "agent", "Correction to heat formula", category="correction")

        by_author = gb.glassbox_recall(author_id="claude")
        self.assertEqual(len(by_author), 2)

        by_category = gb.glassbox_recall(category="observation")
        self.assertEqual(len(by_category), 1)
        self.assertEqual(by_category[0]["author_id"], "gemini")

        by_query = gb.glassbox_recall(query="heat")
        self.assertEqual(len(by_query), 1)

    def test_supersedes_chain(self):
        """Versioning — a correction links to what it supersedes."""
        e1 = gb.glassbox_learn("agent_a", "test", "Heat decays linearly", category="observation")
        e2 = gb.glassbox_learn("agent_a", "test", "Heat decays hyperbolically, not linearly",
                               category="correction", supersedes_id=e1["id"])
        self.assertEqual(e2["supersedes_id"], e1["id"])

    def test_stats(self):
        gb.glassbox_learn("arko", "operator", "Founding entry")
        gb.glassbox_learn("claude", "agent", "Learned entry")
        stats = gb.glassbox_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["authors"]["arko"], 1)
        self.assertEqual(stats["authors"]["claude"], 1)


if __name__ == "__main__":
    unittest.main()
