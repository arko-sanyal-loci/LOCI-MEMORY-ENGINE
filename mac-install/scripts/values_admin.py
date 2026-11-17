#!/usr/bin/env python3
"""values_admin.py — the ONLY path that can add or modify a Values row.

Refuses to run unless invoked under sudo (effective UID = 0). Since sudo on
macOS requires your account password (or Touch ID) to elevate, this proves
that Arko-with-Mac-password is physically at the terminal. Arc has no path
here without you.

Usage (all require sudo):
  sudo python3 values_admin.py --list
  sudo python3 values_admin.py --add    --entity value.humility --key V3 --value "..."
  sudo python3 values_admin.py --update --entity value.hope --key V2 --value "..."   # revises text; heat stays 1
  sudo python3 values_admin.py --remove --entity value.hope --key V2                  # rare; audited hard

Every op re-drops+re-creates the immutability triggers around the single
transaction, then hard re-locks the DB (chflags uchg + chmod 400).
"""
from __future__ import annotations
import argparse, json, os, sqlite3, subprocess, sys, time
from pathlib import Path

DB    = Path("/Volumes/DevDrive/.loci-facts.db")
STATE = Path("/Volumes/DevDrive/Memory-state")
AUDIT = STATE / "audit.jsonl"

VALUES_TRIGGERS_SQL = """
DROP TRIGGER IF EXISTS values_immutable_update;
DROP TRIGGER IF EXISTS values_immutable_delete;
DROP TRIGGER IF EXISTS values_immutable_insert;
CREATE TRIGGER values_immutable_update
  BEFORE UPDATE ON loci_facts
  FOR EACH ROW WHEN OLD.tier = 'VALUES'
  BEGIN
    SELECT RAISE(ABORT, 'VALUES rows are immutable — use values_admin.py under sudo');
  END;
CREATE TRIGGER values_immutable_delete
  BEFORE DELETE ON loci_facts
  FOR EACH ROW WHEN OLD.tier = 'VALUES'
  BEGIN
    SELECT RAISE(ABORT, 'VALUES rows are immutable — use values_admin.py under sudo');
  END;
CREATE TRIGGER values_immutable_insert
  BEFORE INSERT ON loci_facts
  FOR EACH ROW WHEN NEW.tier = 'VALUES'
  BEGIN
    SELECT RAISE(ABORT, 'VALUES tier requires values_admin.py (sudo)');
  END;
"""

DROP_TRIGGERS_SQL = """
DROP TRIGGER IF EXISTS values_immutable_update;
DROP TRIGGER IF EXISTS values_immutable_delete;
DROP TRIGGER IF EXISTS values_immutable_insert;
"""

def require_sudo():
    if os.geteuid() != 0:
        sys.exit("[values_admin] must be run under sudo — only Arko-with-Mac-password may touch Values.")


def wartime_verify(level: str):
    """Wartime protocol: extra identity challenge for destructive/unethical ops."""
    from pathlib import Path as _P
    v = _P(__file__).resolve().parent / "verify_identity.py"
    if not v.exists() or not (_P.home() / ".config/loci/identity.json").exists():
        print(f"[values_admin] wartime identity not set; run sudo python3 {v.parent}/set_identity.py to enable extra check.", file=sys.stderr)
        return
    r = subprocess.run(["python3", str(v), "--level", level])
    if r.returncode != 0:
        sys.exit(f"[values_admin] identity check failed — refusing {level} op")

def audit(rec: dict):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time())
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")

def unlock():
    subprocess.run(["chflags", "nouchg", str(DB)], check=False)
    os.chmod(DB, 0o600)

def lock():
    os.chmod(DB, 0o400)
    subprocess.run(["chflags", "uchg", str(DB)], check=False)

def with_open_db(fn, op_name: str, **op_args):
    unlock()
    try:
        con = sqlite3.connect(DB)
        con.executescript(DROP_TRIGGERS_SQL)
        try:
            result = fn(con, **op_args)
            con.commit()
        finally:
            con.executescript(VALUES_TRIGGERS_SQL)
            con.commit()
            con.close()
    finally:
        lock()
    audit({"event": f"values_admin.{op_name}", "args": op_args, "invoker": "sudo-arko"})
    return result

def do_list(con):
    rows = con.execute(
        "SELECT entity, key, value, source_ts, version FROM loci_facts "
        "WHERE tier='VALUES' AND superseded_by IS NULL "
        "ORDER BY source_ts ASC"
    ).fetchall()
    print(f"[values_admin] {len(rows)} VALUES rows:")
    for r in rows:
        print(f"  {r[0]:25} {r[1]:35}  v{r[4]}  ts={r[3]}")
        print(f"    {r[2]}")
    return rows

def do_add(con, *, entity, key, value):
    now = int(time.time())
    con.execute(
        "INSERT INTO loci_facts (entity,key,value,value_type,embedding,"
        "source_trust,source_session,source_ts,heat,last_access_ts,"
        "version,prev_version_id,superseded_by,tier,created_ts,updated_ts) "
        "VALUES (?,?,?,'value',NULL,1.0,'values_admin',?,1.0,?,1,NULL,NULL,'VALUES',?,?)",
        (entity, key, value, now, now, now, now),
    )
    print(f"[values_admin] added VALUES/{entity}/{key}")

def do_update(con, *, entity, key, value):
    now = int(time.time())
    # supersede in place — new version, same entity/key
    row = con.execute("SELECT id, version FROM loci_facts WHERE entity=? AND key=? AND tier='VALUES' AND superseded_by IS NULL", (entity, key)).fetchone()
    if not row: sys.exit(f"[values_admin] no existing VALUES row at {entity}/{key}")
    old_id, ver = row
    con.execute("UPDATE loci_facts SET superseded_by=? WHERE id=?", (-1, old_id))  # marker; new row will supersede
    cur = con.execute(
        "INSERT INTO loci_facts (entity,key,value,value_type,embedding,"
        "source_trust,source_session,source_ts,heat,last_access_ts,"
        "version,prev_version_id,superseded_by,tier,created_ts,updated_ts) "
        "VALUES (?,?,?,'value',NULL,1.0,'values_admin',?,1.0,?,?,?,NULL,'VALUES',?,?)",
        (entity, key, value, now, now, ver+1, old_id, now, now),
    )
    con.execute("UPDATE loci_facts SET superseded_by=? WHERE id=?", (cur.lastrowid, old_id))
    print(f"[values_admin] updated VALUES/{entity}/{key} → v{ver+1}")

def do_remove(con, *, entity, key):
    row = con.execute("SELECT id FROM loci_facts WHERE entity=? AND key=? AND tier='VALUES' AND superseded_by IS NULL", (entity, key)).fetchone()
    if not row: sys.exit(f"[values_admin] no VALUES row at {entity}/{key}")
    # confirm again — this is destructive
    print(f"[values_admin] about to REMOVE VALUES/{entity}/{key}")
    confirm = input("type YES-I-CONFIRM-REMOVE to proceed: ")
    if confirm != "YES-I-CONFIRM-REMOVE":
        sys.exit("[values_admin] aborted")
    con.execute("DELETE FROM loci_facts WHERE id=?", (row[0],))
    print(f"[values_admin] removed VALUES/{entity}/{key}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--add", action="store_true")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--remove", action="store_true")
    ap.add_argument("--entity")
    ap.add_argument("--key")
    ap.add_argument("--value")
    args = ap.parse_args()

    require_sudo()

    if args.list:
        with_open_db(do_list, "list")
    elif args.add:
        for f in ("entity","key","value"):
            if not getattr(args, f): sys.exit(f"[values_admin] --add needs --{f}")
        with_open_db(do_add, "add", entity=args.entity, key=args.key, value=args.value)
    elif args.update:
        for f in ("entity","key","value"):
            if not getattr(args, f): sys.exit(f"[values_admin] --update needs --{f}")
        wartime_verify("destructive")
        with_open_db(do_update, "update", entity=args.entity, key=args.key, value=args.value)
    elif args.remove:
        for f in ("entity","key"):
            if not getattr(args, f): sys.exit(f"[values_admin] --remove needs --{f}")
        wartime_verify("destructive")
        with_open_db(do_remove, "remove", entity=args.entity, key=args.key)
    else:
        ap.print_help()

if __name__ == "__main__":
    main()
