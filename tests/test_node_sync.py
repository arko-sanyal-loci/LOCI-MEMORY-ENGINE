import unittest
import os
import tempfile
import json
from loci_engine.node_sync_daemon import (
    VersionVector,
    CRDTMerger,
    WALChangeDetector,
    MerkleTree,
    SyncDelta,
    NodeSyncDaemon,
)
from loci_engine.storage import StorageEngine


class TestVersionVector(unittest.TestCase):
    def test_tick_increments(self):
        vv = VersionVector("node_a")
        self.assertEqual(vv.tick(), 1)
        self.assertEqual(vv.tick(), 2)
        self.assertEqual(vv.snapshot(), {"node_a": 2})

    def test_merge_takes_max(self):
        vv = VersionVector("node_a")
        vv.tick()
        vv.merge({"node_b": 5, "node_a": 0})
        snap = vv.snapshot()
        self.assertEqual(snap["node_b"], 5)
        self.assertGreaterEqual(snap["node_a"], 2)

    def test_dominates(self):
        vv = VersionVector("node_a")
        vv.tick()
        vv.tick()
        self.assertTrue(vv.dominates({"node_a": 1}))
        self.assertFalse(vv.dominates({"node_a": 1, "node_b": 1}))


class TestCRDTMerger(unittest.TestCase):
    def test_insert_when_local_missing(self):
        remote = {"id": "f1", "content_hash": "abc", "heat": 0.9, "status": "active", "updated_at": "2026-01-01"}
        merged, action = CRDTMerger.merge_item(None, remote)
        self.assertEqual(action, "insert")
        self.assertEqual(merged["id"], "f1")

    def test_lww_heat_update(self):
        local = {"id": "f1", "content_hash": "abc", "heat": 0.5, "status": "active", "updated_at": "2026-01-01"}
        remote = {"id": "f1", "content_hash": "abc", "heat": 0.9, "status": "active", "updated_at": "2026-01-02"}
        merged, action = CRDTMerger.merge_item(local, remote)
        self.assertEqual(action, "update")
        self.assertEqual(merged["heat"], 0.9)

    def test_status_lattice_escalation(self):
        local = {"id": "f1", "content_hash": "abc", "heat": 0.5, "status": "active", "updated_at": "2026-01-01"}
        remote = {"id": "f1", "content_hash": "abc", "heat": 0.5, "status": "superseded", "updated_at": "2026-01-01"}
        merged, action = CRDTMerger.merge_item(local, remote)
        self.assertEqual(action, "update")
        self.assertEqual(merged["status"], "superseded")

    def test_noop_when_identical(self):
        item = {"id": "f1", "content_hash": "abc", "heat": 0.5, "status": "active", "updated_at": "2026-01-01"}
        merged, action = CRDTMerger.merge_item(item, dict(item))
        self.assertEqual(action, "noop")

    def test_conflict_on_different_content(self):
        local = {"id": "f1", "content_hash": "abc", "heat": 0.5, "status": "active"}
        remote = {"id": "f1", "content_hash": "xyz", "heat": 0.5, "status": "active"}
        merged, action = CRDTMerger.merge_item(local, remote)
        self.assertEqual(action, "conflict")


class TestMerkleTree(unittest.TestCase):
    def test_deterministic_root(self):
        items = [
            {"id": "a", "content_hash": "h1", "status": "active", "heat": 0.5},
            {"id": "b", "content_hash": "h2", "status": "active", "heat": 0.8},
        ]
        root1 = MerkleTree.compute_tree_root(items)
        root2 = MerkleTree.compute_tree_root(items)
        self.assertEqual(root1, root2)

    def test_different_items_different_root(self):
        items_a = [{"id": "a", "content_hash": "h1", "status": "active", "heat": 0.5}]
        items_b = [{"id": "b", "content_hash": "h2", "status": "active", "heat": 0.5}]
        self.assertNotEqual(
            MerkleTree.compute_tree_root(items_a),
            MerkleTree.compute_tree_root(items_b),
        )

    def test_empty_tree(self):
        root = MerkleTree.compute_tree_root([])
        self.assertIsNotNone(root)


class TestSyncDelta(unittest.TestCase):
    def test_encode_decode_roundtrip(self):
        items = [{"id": "f1", "content_hash": "abc", "heat": 0.9}]
        encoded = SyncDelta.encode("node_a", {"node_a": 1}, items)
        decoded = SyncDelta.decode(encoded)
        self.assertEqual(decoded["node_id"], "node_a")
        self.assertEqual(decoded["items"][0]["id"], "f1")
        self.assertIn("merkle_root", decoded)


class TestNodeSyncDaemon(unittest.TestCase):
    def setUp(self):
        self.temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
        self.temp_db.close()
        self.storage = StorageEngine(db_path=self.temp_db.name)
        self.daemon = NodeSyncDaemon(db_path=self.temp_db.name, node_id="test_node")

    def tearDown(self):
        os.unlink(self.temp_db.name)

    def test_no_delta_on_empty_db(self):
        result = self.daemon.run_once()
        self.assertFalse(result["has_delta"])

    def test_delta_after_insert(self):
        self.storage.insert_fact(item_id="sync_test_1", namespace="test", canonical_text="sync test fact")
        result = self.daemon.run_once()
        self.assertTrue(result["has_delta"])
        self.assertGreater(result["delta_size"], 0)

    def test_anti_entropy_state(self):
        self.storage.insert_fact(item_id="ae_1", namespace="test", canonical_text="anti-entropy test")
        state = self.daemon.get_anti_entropy_state()
        self.assertEqual(state["node_id"], "test_node")
        self.assertEqual(state["item_count"], 1)
        self.assertIn("merkle_root", state)

    def test_remote_delta_merge(self):
        remote_delta = {
            "node_id": "remote_node",
            "version_vector": {"remote_node": 1},
            "items": [{
                "id": "remote_fact_1",
                "namespace": "test",
                "item_type": "fact",
                "canonical_text": "remote fact",
                "lexical_text": "remote fact",
                "source_event_id": "evt_sync",
                "source_actor": "remote",
                "source_trust": 0.9,
                "confidence": 1.0,
                "sensitivity": "local_only",
                "era": "mid",
                "alpha": 0.01,
                "heat": 0.85,
                "last_observed_at": "2026-01-01T00:00:00+00:00",
                "valid_from": "2026-01-01T00:00:00+00:00",
                "status": "active",
                "content_hash": "deadbeef",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "supersedes_id": None,
                "structured_value": None,
                "embedding_ref": None,
                "source_uri": None,
                "valid_until": None,
                "metadata_json": "{}",
            }],
        }
        applied = self.daemon._apply_remote_delta(remote_delta)
        self.assertEqual(applied, 1)
        self.assertEqual(self.daemon._stats["merges_applied"], 1)


if __name__ == "__main__":
    unittest.main()
