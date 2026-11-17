#!/usr/bin/env python3
"""
sign_patch.py — utility: read unsigned patch on stdin, print signed patch on stdout.

Used by extractors after they build a patch. loci_writer.py verifies with the
same HMAC key.
"""
from __future__ import annotations
import hashlib, hmac, json, os, sys
from pathlib import Path

KEY_PATH = Path.home() / ".config" / "loci" / "signing.key"


def sign(patch: dict) -> dict:
    if not KEY_PATH.exists():
        sys.exit(f"[sign_patch] missing signing key at {KEY_PATH}")
    key = KEY_PATH.read_bytes().strip()
    canonical = f'{patch["signer"]}|{patch["target"]}|{patch["op"]}|{hashlib.sha256(patch["content"].encode()).hexdigest()}'.encode()
    patch["hmac_sha256"] = hmac.new(key, canonical, hashlib.sha256).hexdigest()
    return patch


if __name__ == "__main__":
    patch = json.loads(sys.stdin.read())
    print(json.dumps(sign(patch), sort_keys=True))
