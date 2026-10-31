#!/usr/bin/env python3
"""Tests for the Agent Communications Hub."""

import os
import json
import tempfile
import unittest

import loci_engine.agent_hub as hub
import loci_engine.glassbox as gb


class TestAgentHub(unittest.TestCase):

    def setUp(self):
        self._reg_tmp = tempfile.NamedTemporaryFile(suffix=".json", delete=False)
        self._reg_tmp.close()
        hub.AGENT_REGISTRY_PATH = self._reg_tmp.name
        with open(self._reg_tmp.name, "w") as f:
            json.dump({"agents": {}, "channels": {}}, f)

        self._gb_tmp = tempfile.NamedTemporaryFile(suffix=".jsonl", delete=False)
        self._gb_tmp.close()
        gb.GLASSBOX_PATH = self._gb_tmp.name
        with open(self._gb_tmp.name, "w"):
            pass

    def tearDown(self):
        os.unlink(self._reg_tmp.name)
        os.unlink(self._gb_tmp.name)

    def test_register_and_list(self):
        hub.register_agent("claude", "cloud_api", model="opus-4.6", vram_mb=0)
        hub.register_agent("qwen_local", "local_model", model="qwen2.5:14b", vram_mb=9000)
        agents = hub.get_all_agents()
        self.assertEqual(len(agents), 2)
        ids = {a["agent_id"] for a in agents}
        self.assertEqual(ids, {"claude", "qwen_local"})

    def test_message_routing(self):
        hub.register_agent("agent_a", "local_model")
        hub.register_agent("agent_b", "local_model")
        hub.send_message("agent_a", "agent_b", "request", "Need help with classification")
        msgs = hub.get_messages("agent_b")
        self.assertEqual(len(msgs), 1)
        self.assertIn("Need help", msgs[0]["content"])

    def test_messages_visible_in_glassbox(self):
        """Every message routes through the glassbox — no hidden channels."""
        hub.register_agent("sender", "cloud_api")
        hub.register_agent("receiver", "local_model")
        hub.send_message("sender", "receiver", "learning", "Discovered new pattern")
        entries = gb.glassbox_recall(query="Discovered new pattern")
        self.assertGreater(len(entries), 0)

    def test_feedback_with_reason(self):
        hub.register_agent("critic", "cloud_api")
        hub.register_agent("author", "local_model")
        msg = hub.offer_feedback("critic", "author",
                                 feedback="Heat decay should be hyperbolic not linear",
                                 reason="Linear decay violates A1 evidence accumulation")
        self.assertIn("FEEDBACK:", msg["content"])
        self.assertIn("REASON:", msg["content"])

    def test_heartbeat_updates_state(self):
        hub.register_agent("worker", "local_model")
        hub.agent_heartbeat("worker", status="busy", current_task="Classifying entities",
                           needs=["more context on entity types"], gpu_usage_mb=4500)
        agents = hub.get_all_agents()
        worker = [a for a in agents if a["agent_id"] == "worker"][0]
        self.assertEqual(worker["status"], "busy")
        self.assertEqual(worker["current_task"], "Classifying entities")
        self.assertEqual(worker["needs"], ["more context on entity types"])


if __name__ == "__main__":
    unittest.main()
