"""Every module in the shipped packages must import.

The RAG pipeline once imported loci_engine.vectors, a module that only existed in
the legacy loci-memory-engine-1 repo. No test imported the pipeline, so the
break went unnoticed. This test imports everything so a missing module fails CI.
"""
import importlib
import os
import pkgutil
import tempfile
import unittest

# Some modules open their store at import time; keep that out of $HOME.
_TMP = tempfile.mkdtemp(prefix="loci-import-test-")
os.environ.setdefault("LOCI_DB_PATH", os.path.join(_TMP, "context2.db"))
os.environ.setdefault("LOCI_GLASSBOX_PATH", os.path.join(_TMP, "glassbox_ledger.jsonl"))

PACKAGES = ["loci_engine", "coordination_bus", "rag"]


class ImportAllTest(unittest.TestCase):
    def test_every_module_imports(self):
        failures = []
        for name in PACKAGES:
            pkg = importlib.import_module(name)
            for mod in pkgutil.walk_packages(pkg.__path__, prefix=f"{name}."):
                try:
                    importlib.import_module(mod.name)
                except Exception as exc:  # noqa: BLE001 - report every failure
                    failures.append(f"{mod.name}: {type(exc).__name__}: {exc}")
        self.assertEqual(failures, [], "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
