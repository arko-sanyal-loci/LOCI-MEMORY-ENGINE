"""Unified comms/threads routing layer — Aethel OS.

OBSERVE-ONLY, BY DESIGN: threads.py does not block, gate, retry, or act.
It computes, records, and routes — the caller wires the result.
"""
from __future__ import annotations

import re
import time
from typing import Any

from loci_engine import ethics

TRAILER_PATTERN = re.compile(r'(?i)(Closes|Helps|Mitigates|RFP|ITP):\s*#?(\S+)')

TRAILER_ROLE_TAGS: dict[str, str] = {
    'closes':    'thread_conclusion_stop',
    'helps':     'thread_evidence_report',
    'mitigates': 'thread_evidence_mitigate',
    'rfp':       'thread_evidence_rfp',
    'itp':       'thread_evidence_itp',
}

CONCLUSION_ROLE_TAGS = frozenset({'thread_conclusion_stop'})
EVIDENCE_ROLE_TAGS = frozenset({
    'thread_evidence_report', 'thread_evidence_mitigate',
    'thread_evidence_rfp', 'thread_evidence_itp',
})


def post_evidence(ledger, topic, author_id, summary, trailer_keyword,
                  engaged_with_substance=True, source_description="", now=None):
    now = time.time() if now is None else now
    keyword = trailer_keyword.lower()
    role_tag = TRAILER_ROLE_TAGS.get(keyword, f'thread_evidence_{keyword}')
    health = ethics.communication_health_check(engaged_with_substance=engaged_with_substance)
    source_id = f"{trailer_keyword.upper()}:{summary[:80]}"
    result = ethics.record_evidence_source(
        ledger=ledger, topic=topic, source_id=source_id,
        description=source_description or f"[{trailer_keyword}] {summary}",
        communication_health=health, now=now,
    )
    return {**result, 'role_tag': role_tag, 'topic': topic}


def post_conclusion(ledger, topic, author_id, conclusion,
                    acknowledged_prior_hashes, now=None):
    now = time.time() if now is None else now
    return ethics.record_conclusion(
        ledger=ledger, author_id=author_id, topic=topic, conclusion=conclusion,
        acknowledged_prior_hashes=acknowledged_prior_hashes, now=now,
    )


def parse_trailers(text):
    matches = []
    for m in TRAILER_PATTERN.finditer(text):
        keyword = m.group(1)
        topic = m.group(2)
        role_tag = TRAILER_ROLE_TAGS.get(keyword.lower(), f'thread_evidence_{keyword.lower()}')
        matches.append({'keyword': keyword, 'topic': topic, 'role_tag': role_tag,
                        'is_conclusion': role_tag in CONCLUSION_ROLE_TAGS})
    return matches


def route_commit_message(ledger, commit_message, author_id,
                         acknowledged_prior_hashes=None, engaged_with_substance=True, now=None):
    now = time.time() if now is None else now
    ack = acknowledged_prior_hashes or {}
    results = []
    for trailer in parse_trailers(commit_message):
        topic = trailer['topic']
        keyword = trailer['keyword']
        if trailer['is_conclusion']:
            result = post_conclusion(ledger=ledger, topic=topic, author_id=author_id,
                                     conclusion=commit_message,
                                     acknowledged_prior_hashes=ack.get(topic, []), now=now)
        else:
            result = post_evidence(ledger=ledger, topic=topic, author_id=author_id,
                                   summary=commit_message, trailer_keyword=keyword,
                                   engaged_with_substance=engaged_with_substance, now=now)
        results.append({**result, 'keyword': keyword, 'topic': topic,
                        'role_tag': trailer['role_tag']})
    return results


def open_threads(ledger):
    topic_evidence = {}
    closed_topics = set()
    for entry in ledger.entries():
        payload = entry.get('payload', {})
        role_tag = payload.get('role_tag', entry.get('role_tag', ''))
        topic = payload.get('topic') or payload.get('extra_payload', {}).get('topic')
        if topic is None:
            continue
        if role_tag in CONCLUSION_ROLE_TAGS:
            if payload.get('accepted', True):
                closed_topics.add(topic)
        elif role_tag in EVIDENCE_ROLE_TAGS:
            rec = topic_evidence.setdefault(topic, {
                'topic': topic, 'evidence_count': 0, 'last_activity': 0.0, 'authors': []})
            rec['evidence_count'] += 1
            ts = entry.get('ts', 0.0)
            if ts > rec['last_activity']:
                rec['last_activity'] = ts
            aid = entry.get('author_id', '')
            if aid and aid not in rec['authors']:
                rec['authors'].append(aid)
    return [v for k, v in topic_evidence.items() if k not in closed_topics]


def thread_status(ledger, topic, conn=None):
    topic_entries = [
        e for e in ledger.entries()
        if (e.get('payload', {}).get('topic') == topic or
            e.get('payload', {}).get('extra_payload', {}).get('topic') == topic)
    ]
    conclusion_entry = None
    for e in topic_entries:
        role_tag = e.get('payload', {}).get('role_tag', '')
        if role_tag in CONCLUSION_ROLE_TAGS and e.get('payload', {}).get('accepted', True):
            conclusion_entry = e.get('payload')
            break
    completeness = ethics.data_completeness_check(ledger=ledger, topic=topic)
    status = {'topic': topic, 'data_completeness': completeness,
              'council_gate': None, 'open': conclusion_entry is None,
              'conclusion': conclusion_entry}
    if conn is not None:
        try:
            from loci_engine import aethel_council
            status['council_gate'] = aethel_council.has_every_member_been_heard(
                conn=conn, topic=topic)
        except Exception as exc:
            status['council_gate'] = {'error': str(exc)}
    return status


def known_topics(ledger):
    seen = set()
    for entry in ledger.entries():
        payload = entry.get('payload', {})
        t = payload.get('topic') or payload.get('extra_payload', {}).get('topic')
        if t:
            seen.add(t)
    return sorted(seen)
