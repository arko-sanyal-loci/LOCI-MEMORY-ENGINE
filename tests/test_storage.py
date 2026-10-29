import unittest
import os
import tempfile
from loci_engine.storage import StorageEngine

class TestStorageEngine(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False)
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

if __name__ == "__main__":
    unittest.main()
