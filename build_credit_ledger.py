#!/usr/bin/env python3
"""
build_credit_ledger.py — one-time builder for ledger/credit_ledger.jsonl.

Uses loci_engine.ethics.ProvenanceLedger (A4: SHA256(ts||author_id||
role_tag||content), hash-chained, tamper-evident) as the single credit
record for this codebase's real git history — not a separate, parallel
scheme. Every entry's payload includes the actual commit hash from `git
log`, so each credit claim is checkable against the real repository,
not just asserted.

Run once per machine/session that has verified commits to add — it
replays any existing ledger file first (ProvenanceLedger's own
_replay_from_disk), so re-running this script is safe and additive, not
destructive, as long as you only append NEW verified commits below.

Per this project's own attribution discipline (loci-ethical-reasoning-
core skill): credit only what the source actually shows. Every payload
below is built directly from `git log` output, not from memory or
inference about who did what.
"""
import subprocess
import sys

from loci_engine.ethics import ProvenanceLedger

LEDGER_PATH = "ledger/credit_ledger.jsonl"


import re

_COAUTHOR_RE = re.compile(r"^Co-Authored-By:\s*(.+?)\s*(?:<.*>)?\s*$", re.IGNORECASE | re.MULTILINE)


def git_show(commit_hash: str) -> dict:
    """Pull real, verifiable metadata for one commit — never fabricated."""
    out = subprocess.run(
        ["git", "show", "-s", "--format=%H|%ai|%an|%ae|%s", commit_hash],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    full_hash, author_date, author_name, author_email, subject = out.split("|", 4)

    # Check the full commit body for a Co-Authored-By trailer — this is
    # where git ACTUALLY does record agent/session identity, when the
    # committing session included it. Use it when present; only fall
    # back to "not recorded" when the commit genuinely has none (per
    # this project's attribution discipline: credit only what the
    # source actually shows, never guess).
    body = subprocess.run(
        ["git", "show", "-s", "--format=%B", commit_hash],
        capture_output=True, text=True, check=True,
    ).stdout
    coauthor_match = _COAUTHOR_RE.search(body)
    agent_identity = (
        coauthor_match.group(1).strip()
        if coauthor_match
        else "not separately recorded in git history for this commit"
    )

    return {
        "commit_hash": full_hash,
        "author_date": author_date,
        "author_name": author_name,
        "author_email": author_email,
        "subject": subject,
        "agent_session_identity": agent_identity,
    }


def get_all_verified_commits() -> list:
    """Every commit on origin/main's real history — not a hand-picked
    subset. Returns hashes oldest-first so the ledger's seq order
    matches the actual commit order."""
    out = subprocess.run(
        ["git", "log", "--format=%H", "--reverse", "origin/main"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return [h for h in out.split("\n") if h]


VERIFIED_COMMITS = get_all_verified_commits()


def main() -> int:
    ledger = ProvenanceLedger(jsonl_path=LEDGER_PATH)
    existing_hashes = {
        e.payload.get("commit_hash")
        for e in ledger._entries  # noqa: SLF001 — read-only inspection, same pattern ethics.py's own helpers use
        if isinstance(e.payload, dict)
    }

    added = 0
    for commit_hash in VERIFIED_COMMITS:
        if commit_hash in existing_hashes:
            continue
        meta = git_show(commit_hash)
        entry_hash = ledger.append(
            author_id=meta["author_name"],
            role_tag="credit",
            payload=meta,
        )
        print(f"Added credit entry for {commit_hash[:10]} -> ledger entry {entry_hash[:16]}...")
        added += 1

    if not ledger.verify_chain():
        print("CHAIN VERIFICATION FAILED — ledger file may be corrupted.", file=sys.stderr)
        return 1

    print(f"\n{added} new entries added. Total entries: {len(ledger._entries)}.")
    print(f"Chain verified intact (verify_chain() == True).")
    print(f"Head hash: {ledger.head_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
