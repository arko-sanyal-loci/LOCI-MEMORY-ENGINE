"""Offline regression checks for deployment and credential write boundaries."""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]


def run(*args, directory, env=None, check=True):
    return subprocess.run(args, cwd=directory, env=env, check=check,
                          capture_output=True, text=True)


@pytest.fixture
def sync_repo(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()
    run("git", "init", "-q", "-b", "main", directory=upstream)
    run("git", "config", "user.name", "Fixture", directory=upstream)
    run("git", "config", "user.email", "fixture@example.invalid", directory=upstream)
    engine = upstream / "loci_engine"
    engine.mkdir()
    (engine / "sample.py").write_text("value = 1\n")
    run("git", "add", ".", directory=upstream)
    run("git", "commit", "-qm", "Base", directory=upstream)
    node = tmp_path / "node"
    run("git", "clone", "-q", str(upstream), str(node), directory=tmp_path)
    (engine / "sample.py").write_text("value = 2\n")
    (upstream / "next.txt").write_text("upstream\n")
    run("git", "add", ".", directory=upstream)
    run("git", "commit", "-qm", "Changed engine", directory=upstream)
    manifest = run(sys.executable, str(ROOT / "scripts/engine_manifest.py"),
                   directory=upstream).stdout
    (upstream / "manifest.sha256").write_text(manifest)
    run("git", "add", "manifest.sha256", directory=upstream)
    run("git", "commit", "-qm", "Manifest", directory=upstream)
    return upstream, node


def sync(node, *args):
    return run("bash", str(ROOT / "node_sync.sh"), *args, directory=node,
               env={**os.environ, "LOCI_WORKSPACE": str(node)}, check=False)


def test_sync_checks_then_fast_forwards(sync_repo):
    _, node = sync_repo
    file = node / "loci_engine/sample.py"
    assert sync(node).returncode == 0
    assert file.read_text() == "value = 1\n"
    assert sync(node, "--apply").returncode == 0
    assert file.read_text() == "value = 2\n"


@pytest.mark.parametrize("state", ["unstaged", "staged", "untracked"])
def test_sync_preserves_local_work(sync_repo, state):
    _, node = sync_repo
    file = node / ("new.txt" if state == "untracked" else "loci_engine/sample.py")
    file.write_text("local work\n")
    if state == "staged":
        run("git", "add", str(file), directory=node)
    before = run("git", "status", "--porcelain", directory=node).stdout
    assert sync(node, "--apply").returncode != 0
    assert file.read_text() == "local work\n"
    assert run("git", "status", "--porcelain", directory=node).stdout == before


def test_sync_rejects_bad_manifest(sync_repo):
    upstream, node = sync_repo
    (upstream / "manifest.sha256").write_text("0" * 64 + "\n")
    run("git", "commit", "-qam", "Invalid manifest", directory=upstream)
    result = sync(node, "--apply")
    assert result.returncode != 0
    assert "manifest is invalid" in result.stderr
    assert (node / "loci_engine/sample.py").read_text() == "value = 1\n"


def test_sync_preserves_an_ignored_file_that_would_be_overwritten(sync_repo):
    _, node = sync_repo
    (node / ".git/info/exclude").write_text("next.txt\n")
    path = node / "next.txt"
    path.write_text("local ignored data\n")
    assert sync(node, "--apply").returncode != 0
    assert path.read_text() == "local ignored data\n"


def test_legacy_overlay_refuses_without_running_network_commands(tmp_path):
    result = run("/bin/bash", str(ROOT / "sync_to_remote.sh"), directory=tmp_path,
                 env={**os.environ, "PATH": ""}, check=False)
    assert result.returncode == 1
    assert "Remote workspace overlays are disabled" in result.stderr


@pytest.fixture
def extractor(tmp_path):
    source = ROOT / "mac-install/extractors"
    script_dir = tmp_path / "application/extractors"
    script_dir.mkdir(parents=True)
    for name in ("qsymprev_extractor.py", "secrets_guard.py"):
        (script_dir / name).write_bytes((source / name).read_bytes())
    helpers = script_dir.parent / "scripts"
    helpers.mkdir()
    (helpers / "sign_patch.py").write_text("import sys; print(sys.stdin.read())\n")
    (helpers / "loci_writer.py").write_text(
        "import os, sys\nfrom pathlib import Path\n"
        "Path(os.environ['LOCI_DEVDRIVE'], 'captured.json').write_text(sys.stdin.read())\n"
    )
    return script_dir / "qsymprev_extractor.py"


def extract(extractor, root, session_id, text):
    transcripts = root / "Transcripts" / session_id
    transcripts.mkdir(parents=True)
    record = {"type": "user", "message": {"content": text}}
    (transcripts / "session.jsonl").write_text(json.dumps(record) + "\n")
    return run(sys.executable, str(extractor), directory=root,
               env={**os.environ, "LOCI_DEVDRIVE": str(root)}, check=False)


def test_extractor_fingerprints_before_signing(extractor, tmp_path):
    synthetic = "ghp_" + "A" * 36
    result = extract(extractor, tmp_path, "local_example", f"/home/demo/{synthetic} port 8080")
    assert result.returncode == 0, result.stderr
    payload = (tmp_path / "captured.json").read_text()
    assert synthetic not in payload
    assert "<redacted:api_key.github:" in payload
    assert '"value_sha256"' in json.loads(payload)["content"]
    assert "8080" in payload


def test_extractor_blocks_secrets_in_metadata_before_writes(extractor, tmp_path):
    synthetic = "ghp_" + "B" * 36
    result = extract(extractor, tmp_path, "local_" + synthetic, "port 8080")
    assert result.returncode != 0
    assert synthetic not in result.stderr
    assert not (tmp_path / "captured.json").exists()
    assert not (tmp_path / "Memory-state").exists()
