#!/usr/bin/env python3
"""Owner store autoload. Time jumps are injected logical days, not a two-week wait."""

import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from loci_engine.memory_lifecycle import (
    HOST_STATUS,
    conversation_end,
    conversation_start,
    process_turn,
    resolve_config,
)


def _conf(directory: str, autoload: str = "1"):
    return resolve_config(
        {"LOCI_MEMORY_AUTOLOAD": autoload, "LOCI_MEMORY_STORE_DIR": directory},
        store_dir=directory,
    )


def _confirm(config, owner="alice"):
    return process_turn(
        config,
        owner_id=owner,
        conversation_id="seed",
        text="not stored as a fact",
        confirmed={
            "task_key": "mixweight",
            "option_key": "w05",
            "polarity": "positive",
            "outcome_id": "heldout-1",
            "statement": "For task mixweight option w05 observed loss 0.05.",
            "quantity": 0.05,
            "unit": "loss",
        },
    )


class MemoryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = self.tmp.name
        self.config = _conf(self.dir)

    def tearDown(self):
        self.tmp.cleanup()

    def test_default_config_is_on_and_outside_the_repo(self):
        cfg = resolve_config({})
        self.assertTrue(cfg.autoload)
        self.assertTrue(cfg.store_dir.endswith(".local/share/loci-memory-engine"))
        self.assertEqual(HOST_STATUS["grok_bot_host_integration"], "unverified_not_activated")
        self.assertEqual(
            HOST_STATUS["label"],
            "engine default on; actual Grok Bot auto-integration not activated/unverified",
        )
        self.assertFalse(HOST_STATUS["all_future_calls_use_this"])
        self.assertFalse(HOST_STATUS["manual_cli_is_full_turn_memory"])

    def test_two_processes_and_two_conversation_ids_share_one_owner_store(self):
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        env["LOCI_MEMORY_STORE_DIR"] = self.dir
        env["LOCI_MEMORY_AUTOLOAD"] = "1"
        write = subprocess.run(
            [sys.executable, "-c", """
from loci_engine.memory_lifecycle import process_turn, resolve_config
cfg = resolve_config()
process_turn(cfg, owner_id="alice", conversation_id="c1", text="chat",
    confirmed={"task_key":"mixweight","option_key":"w05","polarity":"positive",
               "outcome_id":"heldout-1","statement":"For task mixweight option w05 observed loss 0.05.",
               "quantity":0.05,"unit":"loss"})
"""],
            env=env, check=True, capture_output=True, text=True,
        )
        read = subprocess.run(
            [sys.executable, "-c", """
import json
from loci_engine.memory_lifecycle import conversation_start, resolve_config
cfg = resolve_config()
print(json.dumps(conversation_start(cfg, owner_id="alice", conversation_id="c2",
    opening="choose mixweight option w05")))
"""],
            env=env, check=True, capture_output=True, text=True,
        )
        payload = json_loads(read.stdout)
        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["conversation_id"], "c2")
        self.assertEqual(len(payload["memories"]), 1)
        memory = payload["memories"][0]
        self.assertEqual(memory["source_event_ids"], ["heldout-1"])
        self.assertEqual(memory["supplied_by"], "loci_engine.memory_lifecycle")
        self.assertTrue(memory["store_path"].endswith("alice.db"))
        self.assertEqual(payload["qsymprev"][0]["quantity"], 0.05)
        self.assertFalse(payload["embeddings_used"])
        self.assertEqual(write.returncode, 0)

    def test_update_wins_other_owner_sees_nothing_and_unrelated_opening_stays_quiet(self):
        _confirm(self.config)
        process_turn(
            self.config,
            owner_id="alice",
            conversation_id="c3",
            text="chat",
            confirmed={
                "task_key": "mixweight",
                "option_key": "w05",
                "polarity": "negative",
                "outcome_id": "heldout-2",
                "statement": "For task mixweight avoid option w05 observed loss 0.55.",
                "quantity": 0.55,
                "unit": "loss",
            },
        )
        alice = conversation_start(
            self.config, owner_id="alice", conversation_id="c4", opening="mixweight w05",
        )
        self.assertEqual(len(alice["memories"]), 1)
        self.assertEqual(alice["memories"][0]["source_event_ids"], ["heldout-2"])
        self.assertEqual(alice["qsymprev"][0]["quantity"], 0.55)
        self.assertEqual(alice["memories"][0]["polarity"], "negative")
        bob = conversation_start(
            self.config, owner_id="bob", conversation_id="c4", opening="mixweight w05",
        )
        self.assertEqual(bob["memories"], [])
        quiet = conversation_start(
            self.config, owner_id="alice", conversation_id="c5",
            opening="harbor lighthouse fog",
        )
        self.assertEqual(quiet["memories"], [])

    def test_opt_out_skips_without_deleting(self):
        _confirm(self.config)
        db = Path(self.dir) / "alice.db"
        size_before = db.stat().st_size
        off = _conf(self.dir, "0")
        skipped = conversation_start(
            off, owner_id="alice", conversation_id="c9", opening="mixweight w05",
        )
        self.assertEqual(skipped["status"], "skipped")
        self.assertEqual(skipped["memories"], [])
        self.assertGreaterEqual(db.stat().st_size, size_before)
        back = conversation_start(
            self.config, owner_id="alice", conversation_id="c10", opening="mixweight w05",
        )
        self.assertEqual(len(back["memories"]), 1)

    def test_corrupt_store_does_not_invent_recall(self):
        path = Path(self.dir) / "alice.db"
        path.write_text("this is not sqlite", encoding="utf-8")
        result = conversation_start(
            self.config, owner_id="alice", conversation_id="c11", opening="mixweight",
        )
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual(result["memories"], [])
        self.assertFalse(result["invented"])
        self.assertIn("DatabaseError", result["reason"])
        wall = datetime.fromisoformat(result["wall_time"])
        self.assertIsNotNone(wall.tzinfo)
        self.assertLess(abs((datetime.now(timezone.utc) - wall).total_seconds()), 30)

    def test_fourteen_logical_days_is_not_a_real_wait(self):
        process_turn(
            self.config,
            owner_id="alice",
            conversation_id="old",
            text="chat",
            now_day=0.0,
            confirmed={
                "task_key": "mixweight",
                "option_key": "w05",
                "polarity": "positive",
                "outcome_id": "old-1",
                "statement": "For task mixweight option w05 observed loss 0.05.",
                "quantity": 0.05,
                "unit": "loss",
                "expires_on_day": None,
            },
        )
        process_turn(
            self.config,
            owner_id="alice",
            conversation_id="short",
            text="chat",
            now_day=0.0,
            confirmed={
                "task_key": "mixweight",
                "option_key": "w08",
                "polarity": "negative",
                "outcome_id": "short-1",
                "statement": "For task mixweight avoid option w08 observed loss 0.55.",
                "quantity": 0.55,
                "unit": "loss",
                "expires_on_day": 10.0,
            },
        )
        loaded = conversation_start(
            self.config,
            owner_id="alice",
            conversation_id="later",
            opening="mixweight",
            now_day=16.0,
            time_control="injected_logical_day",
        )
        self.assertEqual(loaded["time_control"], "injected_logical_day")
        self.assertFalse(loaded["wall_clock_backdated"])
        ids = {row["option_key"] for row in loaded["memories"]}
        self.assertIn("w05", ids)
        self.assertNotIn("w08", ids)
        wall = datetime.fromisoformat(loaded["wall_time"])
        self.assertLess(abs((datetime.now(timezone.utc) - wall).total_seconds()), 30)
        conversation_end(self.config, owner_id="alice", conversation_id="later")
        skipped = conversation_start(
            self.config, owner_id="alice", conversation_id="no-index", opening="mixweight",
        )
        self.assertEqual(skipped["paper_indexing"]["status"], "skipped")
        self.assertFalse(skipped["paper_indexing"]["actual_index"])
        self.assertEqual(skipped["paper_indexing"]["monotonic_duration_seconds"], 0.0)
        indexed = conversation_start(
            self.config,
            owner_id="alice",
            conversation_id="indexed",
            opening="mixweight",
            run_index=True,
            documents=[{"id": "note", "text": "Public source sentence about mixweight, not a user fact."}],
        )
        self.assertEqual(indexed["paper_indexing"]["status"], "completed")
        self.assertTrue(indexed["paper_indexing"]["actual_index"])
        self.assertEqual(indexed["paper_indexing"]["indexed"], 1)
        self.assertGreater(indexed["paper_indexing"]["monotonic_duration_seconds"], 0.0)


def json_loads(text: str):
    import json
    return json.loads(text)


if __name__ == "__main__":
    unittest.main()
