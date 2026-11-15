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


class TestGlassboxSync(unittest.TestCase):
    """Tests for cross-node sync: apply_remote + new_entries_since."""

    def setUp(self):
        self._tmpfile = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self._tmpfile.close()
        gb.GLASSBOX_PATH = self._tmpfile.name
        with open(self._tmpfile.name, "w"):
            pass

    def tearDown(self):
        os.unlink(self._tmpfile.name)

    def test_apply_remote_new_entry(self):
        """A remote entry not in the local ledger is applied and readable."""
        remote_entry = gb.glassbox_learn("remote_agent", "agent", "Remote insight")
        # Clear ledger to simulate a fresh node
        with open(gb.GLASSBOX_PATH, "w"):
            pass
        applied = gb.glassbox_apply_remote(remote_entry)
        self.assertTrue(applied)
        entries = gb._read_ledger()
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["entry_hash"], remote_entry["entry_hash"])

    def test_apply_remote_idempotent(self):
        """Applying the same remote entry twice is a no-op the second time."""
        remote_entry = gb.glassbox_learn("remote_agent", "agent", "Remote insight")
        with open(gb.GLASSBOX_PATH, "w"):
            pass
        gb.glassbox_apply_remote(remote_entry)
        applied_again = gb.glassbox_apply_remote(remote_entry)
        self.assertFalse(applied_again)
        self.assertEqual(len(gb._read_ledger()), 1)

    def test_new_entries_since_none(self):
        """When last_seen_hash is None, all entries are returned."""
        gb.glassbox_learn("a", "t", "First")
        gb.glassbox_learn("b", "t", "Second")
        entries = gb.glassbox_new_entries_since(None)
        self.assertEqual(len(entries), 2)

    def test_new_entries_since_known_hash(self):
        """Only entries after the known hash are returned."""
        e1 = gb.glassbox_learn("a", "t", "First")
        gb.glassbox_learn("b", "t", "Second")
        gb.glassbox_learn("c", "t", "Third")
        new = gb.glassbox_new_entries_since(e1["entry_hash"])
        self.assertEqual(len(new), 2)
        self.assertEqual(new[0]["content"], "Second")

    def test_new_entries_since_head_returns_empty(self):
        """No new entries when already at the chain head."""
        gb.glassbox_learn("a", "t", "Only entry")
        entries = gb._read_ledger()
        head = entries[-1]["entry_hash"]
        new = gb.glassbox_new_entries_since(head)
        self.assertEqual(new, [])

    def test_ensure_table_creates_schema(self):
        """glassbox_ensure_table creates glassbox_entry table in SQLite."""
        import sqlite3
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            # Create a minimal SQLite DB (simulate existing DB)
            conn = sqlite3.connect(db_path)
            conn.close()
            gb.glassbox_ensure_table(db_path)
            conn = sqlite3.connect(db_path)
            tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            conn.close()
            self.assertIn("glassbox_entry", tables)
        finally:
            os.unlink(db_path)

    def test_write_to_db_mirrors_entry(self):
        """_write_to_db inserts the entry into glassbox_entry table."""
        import sqlite3
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name
        try:
            conn = sqlite3.connect(db_path)
            conn.close()
            entry = gb.glassbox_learn("arko", "operator", "DB mirror test")
            gb._write_to_db(entry, db_path)
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM glassbox_entry WHERE id = ?", (entry["id"],)).fetchone()
            conn.close()
            self.assertIsNotNone(row)
            self.assertEqual(row["entry_hash"], entry["entry_hash"])
            self.assertEqual(row["author_id"], "arko")
        finally:
            os.unlink(db_path)


if __name__ == "__main__":
    unittest.main()
