import os
import tempfile
import unittest

from loci_engine.secrets_guard import contains_secret, find_secrets, redact

# Built at runtime so this file never contains a literal credential.
ANTHROPIC = "sk-ant-api03-" + "A" * 40
GITHUB = "ghp_" + "b" * 36
AWS = "AKIA" + "ABCDEFGHIJKLMNOP"


class SecretsGuardTests(unittest.TestCase):
    def test_redacts_known_formats(self):
        text = f"key {ANTHROPIC} and {GITHUB} and {AWS} and https://u:pw123@host/x"
        out = redact(text)
        for s in (ANTHROPIC, GITHUB, AWS, "pw123"):
            self.assertNotIn(s, out)
        self.assertIn("<redacted:anthropic:", out)
        self.assertFalse(contains_secret(out))

    def test_fingerprint_is_stable(self):
        self.assertEqual(redact(GITHUB), redact(GITHUB))
        self.assertNotEqual(redact(GITHUB), redact("ghp_" + "c" * 36))

    def test_plain_text_untouched(self):
        self.assertEqual(redact("port 8765 on host a"), "port 8765 on host a")
        self.assertEqual(find_secrets(""), [])

    def test_storage_never_persists_secret(self):
        from loci_engine.storage import StorageEngine
        with tempfile.TemporaryDirectory() as d:
            eng = StorageEngine(os.path.join(d, "ctx.db"))
            eng.insert_fact("f1", "test", f"my key is {ANTHROPIC}")
            with eng._get_connection() as conn:
                rows = [r[0] for r in conn.execute("SELECT canonical_text FROM memory_item")]
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            self.assertTrue(rows and all(ANTHROPIC not in r for r in rows))
            self.assertEqual(mode.lower(), "wal")

    def test_qsymprev_extractor_redacts(self):
        import importlib.util
        import json
        path = os.path.join(os.path.dirname(__file__), "..", "..", "mac-install", "extractors", "qsymprev_extractor.py")
        spec = importlib.util.spec_from_file_location("qsx", path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "local_x", "s.jsonl")
            os.makedirs(os.path.dirname(p))
            with open(p, "w") as f:
                f.write(json.dumps({"type": "user", "message": {"content": f"use {ANTHROPIC}"}}) + "\n")
            from pathlib import Path
            facts = list(mod.scan_session(Path(p)))
        secrets = [f for f in facts if f["value_type"] == "secret"]
        self.assertTrue(secrets)
        for f in secrets:
            self.assertNotIn(ANTHROPIC, json.dumps(f))
            self.assertTrue(f["value"].startswith("<redacted:"))


if __name__ == "__main__":
    unittest.main()
