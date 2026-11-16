import unittest
import os
import tempfile
from loci_engine.storage import StorageEngine

class TestStorageEngine(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.storage = StorageEngine(db_path=self.temp_db.name)

    def tearDown(self):
        os.unlink(self.temp_db.name)

    def test_fact_insertion_and_fts5_search(self):
        self.storage.insert_fact(
            item_id="fact_001",
            namespace="loci_core",
            canonical_text="The loci-workstation operates with an AMD Barcelo GPU and Ubuntu."
        )
        results = self.storage.lexical_search("Barcelo")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["id"], "fact_001")
        self.assertEqual(results[0]["status"], "active")

    def test_append_only_supersede_lineage(self):
        self.storage.insert_fact(
            item_id="v1_ip",
            namespace="network",
            canonical_text="Console IP is 192.168.0.149"
        )
        self.storage.insert_fact(
            item_id="v2_ip",
            namespace="network",
            canonical_text="Console IP updated to 192.168.0.181",
            supersedes_id="v1_ip"
        )
        
        with self.storage._get_connection() as conn:
            v1 = conn.execute("SELECT * FROM memory_item WHERE id = 'v1_ip'").fetchone()
            v2 = conn.execute("SELECT * FROM memory_item WHERE id = 'v2_ip'").fetchone()
            
            self.assertEqual(v1["status"], "superseded")
            self.assertIsNotNone(v1["valid_until"])
            self.assertEqual(v2["status"], "active")
            self.assertEqual(v2["supersedes_id"], "v1_ip")

class TestSessionIngester(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
        self.temp_db.close()
        self.storage = StorageEngine(db_path=self.temp_db.name)
        from loci_engine.session_ingester import SessionIngester
        self.ingester = SessionIngester(
            storage=self.storage,
            session_id="test_session",
            decay_on_init=False,
        )

    def tearDown(self):
        os.unlink(self.temp_db.name)

    def test_ingest_user_turn(self):
        tid = self.ingester.ingest_turn(role="user", content="What GPU do I have?")
        self.assertTrue(tid.startswith("test_session_turn_"))
        rows = self.storage.fetch_active_items(namespace="session")
        self.assertEqual(len(rows), 1)
        self.assertIn("USER", rows[0]["canonical_text"])

    def test_ingest_assistant_turn_lower_heat(self):
        self.ingester.ingest_turn(role="user", content="Hello")
        self.ingester.ingest_turn(role="assistant", content="Hi there")
        rows = self.storage.fetch_active_items(namespace="session")
        heats = {r["canonical_text"].split("]")[0]: r["heat"] for r in rows}
        user_heat = next(v for k, v in heats.items() if "USER" in k)
        asst_heat = next(v for k, v in heats.items() if "ASSISTANT" in k)
        self.assertGreater(user_heat, asst_heat)

    def test_recall_returns_card_result(self):
        self.ingester.ingest_turn(role="user", content="I bought an Intel Arc B50 GPU")
        self.ingester.ingest_turn(role="assistant", content="The Intel Arc B50 has 16GB VRAM")
        result = self.ingester.recall_for_query("what GPU do I have")
        self.assertIn("archetype", result)
        self.assertIn("selected_items", result)
        self.assertGreaterEqual(len(result["selected_items"]), 1)

    def test_turn_count_increments(self):
        self.ingester.ingest_turn("user", "first")
        self.ingester.ingest_turn("user", "second")
        self.assertEqual(self.ingester.turn_count, 2)


if __name__ == "__main__":
    unittest.main()
