#!/usr/bin/env python3
"""
End-to-end benchmark for the unified ethics layer (heat.py + store.py +
ethics.py + aethel_council.py + threads.py), run locally before push.

Exercises the full chain under realistic load and checks the open-interval
invariants hold at scale, not just on the first touch:

  1. store.py   — N entities, each touched M times -> heat never hits 0/1
  2. ethics.py   — trust-pattern tracking through store.py, scar ledger
                   through heat.py directly, full provenance ledger flow
  3. aethel_council.py — council membership + completeness gate
  4. threads.py  — commit-trailer routing over the same ledger

Reports wall-clock timing per stage and asserts correctness invariants.
Exits non-zero on any invariant violation.
"""

import os
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from loci_engine import ethics, store, aethel_council, threads  # noqa: E402

N_ENTITIES = 200
TOUCHES_PER_ENTITY = 50
N_TOPICS = 50
SOURCES_PER_TOPIC = 5


def section(title):
    print(f"\n=== {title} ===")


def bench_store():
    section("store.py — entity persistence under load")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    conn = store.open_db(tmp.name)

    t0 = time.perf_counter()
    for i in range(N_ENTITIES):
        store.remember_entity(conn, f"entity_{i}", gist=f"pattern {i}", now=0.0)
    t_create = time.perf_counter() - t0

    t0 = time.perf_counter()
    final_heats = {}
    for i in range(N_ENTITIES):
        h = 0.0
        for j in range(TOUCHES_PER_ENTITY):
            h = store.touch_entity(conn, f"entity_{i}", hop=0.1, now=float(j))
        final_heats[i] = h
    t_touch = time.perf_counter() - t0

    violations = [
        (eid, h) for eid, h in final_heats.items() if not (0.0 < h < 1.0)
    ]

    print(f"  created {N_ENTITIES} entities in {t_create:.4f}s "
          f"({N_ENTITIES/t_create:.0f}/s)")
    print(f"  {N_ENTITIES * TOUCHES_PER_ENTITY} touches in {t_touch:.4f}s "
          f"({(N_ENTITIES * TOUCHES_PER_ENTITY)/t_touch:.0f}/s)")
    print(f"  open-interval violations: {len(violations)}")
    print(f"  sample final heat (entity_0): {final_heats[0]:.6f}")

    conn.close()
    os.unlink(tmp.name)
    return len(violations) == 0


def bench_ethics_trust():
    section("ethics.py — trust-pattern tracking via store.py")
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    tmp.close()
    conn = store.open_db(tmp.name)

    t0 = time.perf_counter()
    results = []
    for i in range(N_ENTITIES):
        for j in range(5):
            r = ethics.record_pattern_trust_event(
                conn, f"trust_pattern_{i}", hop=0.15, now=float(j)
            )
        results.append(r)
    elapsed = time.perf_counter() - t0

    violations = [
        r for r in results
        if not (0.0 < r["trust_heat"] < 1.0)
        or r["tier"] not in {"hot", "warm", "cool", "cold"}
    ]

    print(f"  {N_ENTITIES * 5} trust events in {elapsed:.4f}s "
          f"({(N_ENTITIES*5)/elapsed:.0f}/s)")
    print(f"  violations: {len(violations)}")
    print(f"  sample result: {results[0]}")

    conn.close()
    os.unlink(tmp.name)
    return len(violations) == 0


def bench_ethics_scar():
    section("ethics.py — scar ledger via heat.py directly (no store.py)")
    ledger = ethics.ProvenanceLedger()

    t0 = time.perf_counter()
    for i in range(N_ENTITIES):
        ethics.record_scar_event(
            ledger, f"scar_{i}", relevance=1.0, valence_weight=-1.0, now=0.0
        )
    heats = [
        ethics.get_scar_heat(ledger, f"scar_{i}", now=float(i % 30))["scar_heat"]
        for i in range(N_ENTITIES)
    ]
    elapsed = time.perf_counter() - t0

    violations = [h for h in heats if not (0.0 < h < 1.0)]
    print(f"  {N_ENTITIES} scars recorded + read back in {elapsed:.4f}s")
    print(f"  violations: {len(violations)}")
    print(f"  sample scar heat: {heats[0]:.6f}")
    return len(violations) == 0


def bench_provenance_flow():
    section("ethics.py — provenance ledger: evidence -> conclusion -> completeness")
    ledger = ethics.ProvenanceLedger()
    health = ethics.communication_health_check(True)

    t0 = time.perf_counter()
    for t in range(N_TOPICS):
        topic = f"topic_{t}"
        for s in range(SOURCES_PER_TOPIC):
            ethics.record_evidence_source(
                ledger, topic=topic, source_id=f"src_{t}_{s}",
                description="bench source", communication_health=health, now=0.0,
            )
        ethics.record_conclusion(
            ledger, author_id="ARKO", topic=topic, conclusion="bench conclusion", now=1.0,
        )
    elapsed = time.perf_counter() - t0

    checks = [
        ethics.data_completeness_check(ledger, f"topic_{t}", now=2.0)
        for t in range(N_TOPICS)
    ]
    # entries_for_topic returns prior CONCLUSIONS only (by its own docstring:
    # "every prior conclusion already on record for this topic") — each
    # topic here got exactly one conclusion recorded, so the right
    # expectation is 1/topic, not sources+conclusion.
    conclusion_counts = [len(ethics.entries_for_topic(ledger, f"topic_{t}")) for t in range(N_TOPICS)]
    violations = [c for c in conclusion_counts if c != 1]

    print(f"  {N_TOPICS} topics x ({SOURCES_PER_TOPIC} sources + 1 conclusion) "
          f"in {elapsed:.4f}s")
    print(f"  conclusion-count mismatches: {len(violations)} (expected 1/topic)")
    print(f"  sample completeness check status: {checks[0]['status']}, "
          f"source_count: {checks[0]['source_count']}")
    return len(violations) == 0


def bench_aethel_council():
    section("aethel_council.py — membership + completeness gate")
    ledger = ethics.ProvenanceLedger()

    t0 = time.perf_counter()
    for i in range(20):
        aethel_council.register_council_member(
            ledger, f"member_{i}", member_kind="human" if i % 2 == 0 else "agent"
        )
    members = aethel_council.list_council_members(ledger)
    elapsed = time.perf_counter() - t0

    print(f"  registered 20 council members in {elapsed:.4f}s")
    print(f"  members tracked: {len(members)}")
    heard_before_input = aethel_council.has_every_member_been_heard(ledger, "council_topic")
    print(f"  heard-check before any input: {heard_before_input}")
    return len(members) == 20


def bench_threads():
    section("threads.py — commit-trailer routing over the shared ledger")
    ledger = ethics.ProvenanceLedger()

    t0 = time.perf_counter()
    routed = []
    for i in range(N_ENTITIES):
        msg = f"Fix thing {i}\n\nHelps: #{i}"
        result = threads.route_commit_message(ledger, msg, author_id=f"commit_{i}", now=0.0)
        routed.append(result)
    elapsed = time.perf_counter() - t0

    failures = [r for r in routed if not r]
    print(f"  routed {N_ENTITIES} commit messages in {elapsed:.4f}s "
          f"({N_ENTITIES/elapsed:.0f}/s)")
    print(f"  routing failures: {len(failures)}")
    print(f"  sample route result: {routed[0]}")
    return len(failures) == 0


def main():
    print("LOCI unified ethics layer — end-to-end benchmark")
    print(f"N_ENTITIES={N_ENTITIES}  TOUCHES_PER_ENTITY={TOUCHES_PER_ENTITY}  "
          f"N_TOPICS={N_TOPICS}")

    t_start = time.perf_counter()
    results = {
        "store": bench_store(),
        "ethics_trust": bench_ethics_trust(),
        "ethics_scar": bench_ethics_scar(),
        "provenance_flow": bench_provenance_flow(),
        "aethel_council": bench_aethel_council(),
        "threads": bench_threads(),
    }
    t_total = time.perf_counter() - t_start

    section("SUMMARY")
    all_pass = all(results.values())
    for name, ok in results.items():
        print(f"  {'PASS' if ok else 'FAIL'}  {name}")
    print(f"\n  total wall time: {t_total:.3f}s")
    print(f"  overall: {'PASS' if all_pass else 'FAIL'}")

    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
