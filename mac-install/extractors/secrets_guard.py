"""
loci_engine/secrets_guard.py
============================
Keep credentials out of memory.

LOCI ingests whole conversations. Conversations contain pasted API keys,
tokens and private keys. Anything written to ``context2.db``, a ``.jsonl``
stream or the Glassbox is permanent by design (append-only, hash-chained,
synced across nodes), so a secret that gets in can never be cleanly taken
out. The only safe policy is to never write one.

``redact()`` replaces every recognised secret with a stable placeholder,
``<redacted:KIND:fp>``, where ``fp`` is the first 8 hex characters of the
secret's SHA-256. The fingerprint lets the memory still say "the same key
was mentioned again" or "the key changed" (useful for qSymPrev versioning)
without storing anything that can be used as the key.

Patterns cover the formats that actually appear in this project's sessions
(Anthropic, OpenAI-style, xAI, GitHub classic and fine-grained, AWS, Slack,
Google, private key blocks, bearer tokens, URL credentials).
"""
from __future__ import annotations

import hashlib
import re
from typing import List, Tuple

SECRET_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("anthropic", re.compile(r"sk-ant-[A-Za-z0-9_\-]{20,200}")),
    ("openai", re.compile(r"sk-(?:proj-)?[A-Za-z0-9_\-]{32,200}")),
    ("xai", re.compile(r"xai-[A-Za-z0-9]{40,200}")),
    ("github", re.compile(r"(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9]{30,255}")),
    ("github", re.compile(r"github_pat_[A-Za-z0-9_]{40,255}")),
    ("aws", re.compile(r"(?:AKIA|ASIA)[A-Z0-9]{16}")),
    ("slack", re.compile(r"xox[abposr]-[A-Za-z0-9\-]{10,200}")),
    ("google", re.compile(r"AIza[0-9A-Za-z_\-]{35}")),
    ("private_key", re.compile(
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]+?-----END [A-Z ]*PRIVATE KEY-----")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9_\-\.=]{20,}")),
    ("url_credentials", re.compile(r"(?<=://)[^/\s:@<]+:[^/\s@]+(?=@)")),
]


def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:8]


def placeholder(kind: str, secret: str) -> str:
    return f"<redacted:{kind}:{fingerprint(secret)}>"


def find_secrets(text: str) -> List[Tuple[str, str]]:
    """``(kind, secret)`` for every secret in ``text`` (overlaps de-duplicated)."""
    hits: List[Tuple[int, int, str, str]] = []
    for kind, rx in SECRET_PATTERNS:
        for m in rx.finditer(text):
            hits.append((m.start(), m.end(), kind, m.group(0)))
    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    out, last_end = [], -1
    for start, end, kind, s in hits:
        if start >= last_end:
            out.append((kind, s))
            last_end = end
    return out


def redact(text: str) -> str:
    """Return ``text`` with every recognised secret replaced by a placeholder."""
    if not text:
        return text
    for kind, secret in find_secrets(text):
        text = text.replace(secret, placeholder(kind, secret))
    return text


def contains_secret(text: str) -> bool:
    return bool(text) and bool(find_secrets(text))


__all__ = ["SECRET_PATTERNS", "contains_secret", "find_secrets", "fingerprint", "placeholder", "redact"]
