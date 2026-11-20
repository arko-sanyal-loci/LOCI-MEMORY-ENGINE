"""manifest.sha256 must match the engine tree, or node_sync.sh resets every node.

node_sync.sh compares origin/main:manifest.sha256 with a hash of loci_engine/.
When the two disagree it runs `git reset --hard` and `git clean -fd`, on every
tick, forever. Regenerate with scripts/ops/update_manifest.sh.
"""
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class ManifestTest(unittest.TestCase):
    def test_manifest_matches_engine_tree(self):
        current = subprocess.run(
            ["bash", "-c", "source scripts/ops/engine_hash.sh && engine_hash"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout.strip()
        recorded = (ROOT / "manifest.sha256").read_text().strip()
        self.assertEqual(
            recorded, current,
            "manifest.sha256 is stale: run scripts/ops/update_manifest.sh and commit it",
        )

    def test_hash_ignores_bytecode(self):
        cache = ROOT / "loci_engine" / "__pycache__"
        cache.mkdir(exist_ok=True)
        probe = cache / "_manifest_probe.pyc"
        before = subprocess.run(
            ["bash", "-c", "source scripts/ops/engine_hash.sh && engine_hash"],
            cwd=ROOT, check=True, capture_output=True, text=True,
        ).stdout
        probe.write_bytes(b"x")
        try:
            after = subprocess.run(
                ["bash", "-c", "source scripts/ops/engine_hash.sh && engine_hash"],
                cwd=ROOT, check=True, capture_output=True, text=True,
            ).stdout
        finally:
            probe.unlink()
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
