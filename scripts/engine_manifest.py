#!/usr/bin/env python3
"""Print the SHA-256 manifest for tracked engine files at a Git revision."""

import hashlib
import subprocess
import sys


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args])


def engine_manifest(revision: str) -> str:
    commit = git("rev-parse", "--verify", "--end-of-options", revision + "^{commit}").strip().decode()
    entries = git("ls-tree", "-r", "-z", "--full-tree", commit, "--", "loci_engine").split(b"\0")
    lines = []
    for entry in filter(None, entries):
        metadata, path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        if b"__pycache__" in path.split(b"/") or path.endswith(b".pyc"):
            continue
        if mode not in (b"100644", b"100755") or kind != b"blob" or b"\n" in path or b"\\" in path:
            raise ValueError("Unsupported engine tree entry in the manifest")
        digest = hashlib.sha256(git("cat-file", "blob", oid.decode())).hexdigest().encode()
        lines.append(digest + b"  " + path + b"\n")
    if not lines:
        raise ValueError("The target revision has no tracked engine files")
    return hashlib.sha256(b"".join(sorted(lines))).hexdigest()


if __name__ == "__main__":
    print(engine_manifest(sys.argv[1] if len(sys.argv) > 1 else "HEAD"))
