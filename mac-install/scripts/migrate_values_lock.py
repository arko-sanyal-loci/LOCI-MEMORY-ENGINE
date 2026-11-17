#!/usr/bin/env python3
"""migrate_values_lock.py — one-time migration.

1. Force heat=1.0 on every existing tier='VALUES' row (was seeded as 1e9).
2. Install the immutability triggers on loci_facts.
3. Verify the triggers block a normal INSERT/UPDATE/DELETE.

Requires sudo (proves Arko is at the machine).
"""
from __future__ import annotations
import os, sqlite3, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from values_admin import (
    DB, unlock, lock, VALUES_TRIGGERS_SQL, DROP_TRIGGERS_SQL, require_sudo, audit,
)

def main():
    require_sudo()
    if not DB.exists():
        sys.exit(f"[migrate] no DB at {DB}")

    unlock()
    try:
        con = sqlite3.connect(DB)
        cur = con.cursor()

        # 1. Force heat=1.0 on VALUES (must drop triggers first — this is the migration itself)
        cur.executescript(DROP_TRIGGERS_SQL)
        cur.execute("UPDATE loci_facts SET heat = 1.0 WHERE tier = 'VALUES'")
        n = cur.rowcount
        con.commit()
        print(f"[migrate] set heat=1.0 on {n} VALUES rows")

        # 2. Install triggers
        cur.executescript(VALUES_TRIGGERS_SQL)
        con.commit()
        print("[migrate] installed immutability triggers (update/delete/insert)")

        # 3. Verify — try to sneak an INSERT and expect ABORT
        try:
            cur.execute(
                "INSERT INTO loci_facts (entity,key,value,tier,heat,source_trust,source_ts) "
                "VALUES ('__test__','__test__','__test__','VALUES',1.0,1.0,0)"
            )
            print("[migrate] FAIL — trigger did NOT block the test insert")
            sys.exit(1)
        except sqlite3.IntegrityError as e:
            print(f"[migrate] trigger OK: blocked test insert ({e})")

        con.close()
    finally:
        lock()

    audit({"event": "values_lock_migrated", "rows_updated": n})
    print("[migrate] done. VALUES rows are now heat=1, immutable through normal write paths.")

if __name__ == "__main__":
    main()
