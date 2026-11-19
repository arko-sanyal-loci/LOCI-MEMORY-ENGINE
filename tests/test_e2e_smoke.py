"""End-to-end smoke test: the paths the user guide documents, run start to finish.

Every example in docs/USER_GUIDE.md is exercised here, so the guide cannot drift
from the code without this file failing. Each test uses a throwaway database and
ledger so it never touches ~/loci-memory-engine.
"""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class TestUserGuideFlow(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "memory.db")
        self.ledger = os.path.join(self.tmp.name, "glassbox.jsonl")

    def tearDown(self):
        self.tmp.cleanup()

    def test_store_and_search_a_fact(self):
        from loci_engine.storage import StorageEngine

        storage = StorageEngine(db_path=self.db)
        storage.insert_fact("gpu_1", "hardware", "Workstation GPU is an Intel Arc B70 Pro with 32GB")
        hits = storage.lexical_search("B70")
        self.assertEqual([h["id"] for h in hits], ["gpu_1"])

    def test_session_ingest_and_card_recall(self):
        from loci_engine.session_ingester import SessionIngester
        from loci_engine.storage import StorageEngine

        storage = StorageEngine(db_path=self.db)
        ingester = SessionIngester(storage=storage, session_id="guide_demo")
        turn_id = ingester.ingest_turn(role="user", content="I upgraded to the Arc B70")
        self.assertEqual(turn_id, "guide_demo_turn_0001")
        result = ingester.recall_for_query("what GPU did the user mention")
        self.assertIn("archetype", result)
        self.assertTrue(any("B70" in json.dumps(i) for i in result["selected_items"]))

    def test_card_classifies_the_four_archetypes(self):
        from loci_engine.card_router import CardRouter

        archetypes = {
            CardRouter.classify_archetype(q)
            for q in (
                "what is my GPU model",
                "I changed my mind, update my preferred editor",
                "across our last few sessions, what did we decide",
                "when did I first mention the B70",
            )
        }
        self.assertTrue(archetypes.issubset({
            "information_extraction", "knowledge_update",
            "multi_session_reasoning", "temporal_reasoning",
        }))

    def test_glassbox_learn_then_verify_chain(self):
        from loci_engine import glassbox

        original = glassbox.GLASSBOX_PATH
        glassbox.GLASSBOX_PATH = self.ledger
        try:
            glassbox.glassbox_learn("arc", "co-author", "HOT tier boundary is 0.80", category="principle")
            glassbox.glassbox_learn("claude", "reviewer", "VRAM admission is 0.70", category="insight")
            verdict = glassbox.glassbox_verify_chain()
            self.assertTrue(verdict["valid"], verdict)
            self.assertEqual(verdict["entries"], 2)
        finally:
            glassbox.GLASSBOX_PATH = original

    def test_heat_thresholds_are_the_documented_ones(self):
        from loci_engine import heat

        self.assertEqual(heat.TIER_HOT_BOUNDARY, 0.80)
        self.assertEqual(heat.TIER_MILD_BOUNDARY, 0.35)
        self.assertEqual(heat.VRAM_ADMISSION_THRESHOLD, 0.70)

    def test_mcp_server_over_stdio(self):
        env = dict(os.environ, LOCI_DB_PATH=self.db, LOCI_GLASSBOX_PATH=self.ledger,
                   PYTHONPATH=str(REPO))
        requests = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        ]
        proc = subprocess.run(
            [sys.executable, "-m", "loci_engine.mcp_server"],
            input="\n".join(json.dumps(r) for r in requests) + "\n",
            capture_output=True, text=True, timeout=60, cwd=self.tmp.name, env=env,
        )
        lines = [json.loads(l) for l in proc.stdout.splitlines() if l.strip().startswith("{")]
        by_id = {r.get("id"): r for r in lines}
        self.assertIn("result", by_id[1], proc.stderr)
        tools = {t["name"] for t in by_id[2]["result"]["tools"]}
        for name in ("memory_search_lexical", "memory_ingest_fact", "glassbox_learn",
                     "glassbox_recall", "glassbox_verify", "session_start", "sync_node_status"):
            self.assertIn(name, tools)


if __name__ == "__main__":
    unittest.main()
