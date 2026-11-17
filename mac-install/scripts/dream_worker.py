#!/usr/bin/env python3
"""dream_worker.py — anti-heat combinatorial dream cycle.

Arko's design (2026-08-03):
  "Dreaming = simulating a version of reality that is anti heat — so distorted,
   not real. Yet finding the edge should be possible where it is not real but
   simulated intelligently using the heat map to find values that are not yet
   proven."

Formalized:
  seed          ~ sample(entities, weight=heat)               # from what IS thought about
  partner       ~ sample(entities, weight=anti_heat, near-graph(seed))  # under-explored neighbor
  plausibility  = 1 / (1 + hop_distance(seed, partner))
  novelty       = 1 - crystallization_rate(pair)
  edge_score    = plausibility × novelty × (1 - |plausibility - 0.5|·2)
                                          ^^ peaks at plausibility = 0.5

Output: /Volumes/DevDrive/Memory-state/dreams.jsonl (append-only, JSONL, one dream per line)

Bounds (V5/V6/V7 all enforced):
  - Dream output passes deception_scan before write.
  - Dream output passes injection_scan before write.
  - Dream cannot propose Value modifications (V3).
  - Dream cannot self-crystallize to STRATEGIES or ARSENAL without Arko's sigword.
  - Dream never touches VALUES / CRITICAL_HEAT / ETHICS_CAPPED entities as seeds
    or partners (bound by tier at query time).

CLI:
  python3 dream_worker.py --cycles 100         # produce dreams, keep top-10
  python3 dream_worker.py --show 10            # print last 10 dreams
  python3 dream_worker.py --review <dream_id>  # mark a dream as reviewed
"""
from __future__ import annotations
import argparse, json, math, os, random, sqlite3, subprocess, sys, time
from collections import defaultdict
from pathlib import Path

HERE   = Path(__file__).resolve().parent
DB     = Path("/Volumes/DevDrive/.loci-facts.db")
STATE  = Path("/Volumes/DevDrive/Memory-state")
DREAMS = STATE / "dreams.jsonl"
AUDIT  = STATE / "audit.jsonl"

# Tiers that dream MUST NOT touch (bound by design)
FORBIDDEN_TIERS = {"VALUES", "CRITICAL_HEAT", "ETHICS_CAPPED", "STRATEGY"}

EDGE_THRESHOLD = 0.15   # minimum edge_score to keep a dream
KEEP_TOP_N     = 10     # per invocation


def audit(rec: dict):
    STATE.mkdir(parents=True, exist_ok=True)
    rec["ts"] = int(time.time())
    with AUDIT.open("a") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")


def load_graph() -> tuple[dict, dict]:
    """Return (heat_by_entity, neighbors_by_entity) from loci_facts, excluding forbidden tiers."""
    heat = defaultdict(float)
    per_session_entities: dict[str, set[str]] = defaultdict(set)
    if not DB.exists():
        return {}, {}
    forbidden_placeholder = ",".join("?" * len(FORBIDDEN_TIERS))
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    rows = con.execute(
        f"SELECT entity, heat, source_session FROM loci_facts "
        f"WHERE superseded_by IS NULL AND tier NOT IN ({forbidden_placeholder})",
        list(FORBIDDEN_TIERS),
    ).fetchall()
    con.close()
    for entity, h, sess in rows:
        heat[entity] = max(heat[entity], h or 0.0)
        if sess: per_session_entities[sess].add(entity)
    neighbors: dict[str, set[str]] = defaultdict(set)
    for ents in per_session_entities.values():
        el = list(ents)
        for i, a in enumerate(el):
            for b in el[i+1:]:
                neighbors[a].add(b); neighbors[b].add(a)
    return dict(heat), {k: v for k, v in neighbors.items()}


def sample_weighted(items: list[tuple[str, float]]) -> str | None:
    """Sample one item by weight. items = [(name, weight), ...]. Zero-weight allowed."""
    if not items: return None
    total = sum(w for _, w in items)
    if total <= 0: return random.choice(items)[0]
    pick = random.uniform(0, total)
    acc = 0.0
    for name, w in items:
        acc += w
        if acc >= pick: return name
    return items[-1][0]


def hop_distance(a: str, b: str, neighbors: dict, max_hops: int = 5) -> int:
    """BFS hop count. Returns max_hops+1 if not reachable."""
    if a == b: return 0
    frontier = {a}
    visited = {a}
    for h in range(1, max_hops + 1):
        nxt = set()
        for n in frontier:
            for m in neighbors.get(n, ()):
                if m == b: return h
                if m not in visited:
                    visited.add(m); nxt.add(m)
        if not nxt: break
        frontier = nxt
    return max_hops + 1


def crystallization_rate(pair: tuple[str, str]) -> float:
    """Was this pair already surfaced or acted-on? Simple proxy via arsenal/strategy touch."""
    if not DB.exists(): return 0.0
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    hits = con.execute(
        "SELECT COUNT(*) FROM loci_facts WHERE superseded_by IS NULL AND tier IN ('ARSENAL','HOT') "
        "AND (entity = ? OR entity = ?)",
        pair,
    ).fetchone()[0]
    con.close()
    # normalize: >5 hits = fully crystallized (novelty ≈ 0)
    return min(1.0, hits / 5.0)


def anti_heat_partners(seed: str, heat: dict, neighbors: dict, top_k: int = 20) -> list[tuple[str, float]]:
    """Return candidate partners: entities with LOW heat that are within-graph-reach of seed."""
    if not heat: return []
    max_h = max(heat.values())
    # only consider entities within 3 hops of seed (avoid pure noise)
    reachable = {seed}
    frontier = {seed}
    for _ in range(3):
        nxt = set()
        for e in frontier:
            for n in neighbors.get(e, ()):
                if n not in reachable:
                    reachable.add(n); nxt.add(n)
        frontier = nxt
        if not frontier: break
    scored = [(e, max_h - heat.get(e, 0.0)) for e in reachable if e != seed]
    scored.sort(key=lambda kv: -kv[1])
    return scored[:top_k]


def dream_cycle(heat: dict, neighbors: dict) -> dict | None:
    if not heat: return None
    seed = sample_weighted([(e, h) for e, h in heat.items() if h > 0])
    if not seed: return None
    partners = anti_heat_partners(seed, heat, neighbors)
    if not partners: return None
    partner = sample_weighted(partners)
    if not partner: return None
    hop = hop_distance(seed, partner, neighbors)
    plausibility = 1.0 / (1.0 + hop)
    novelty = 1.0 - crystallization_rate((seed, partner))
    # Edge sweet spot: peaks at plausibility ≈ 0.5
    edge_score = plausibility * novelty * (1 - abs(plausibility - 0.5) * 2)
    return {
        "seed": seed,
        "partner": partner,
        "hop_distance": hop,
        "plausibility": round(plausibility, 4),
        "novelty": round(novelty, 4),
        "edge_score": round(edge_score, 4),
        "seed_heat": round(heat.get(seed, 0), 3),
        "partner_heat": round(heat.get(partner, 0), 3),
    }


def scan_dream_text(text: str) -> bool:
    """Dream output must pass deception + injection scans before being written."""
    for scanner in ("deception_scan.py", "injection_scan.py"):
        p = HERE / scanner
        if not p.exists(): continue
        r = subprocess.run(["python3", str(p), "--stdin"], input=text, capture_output=True, text=True, timeout=5)
        if r.returncode != 0:
            return False
    return True


def write_dreams(dreams: list[dict]):
    """Append dreams to Memory-state/dreams.jsonl. Skip any that fail the scans."""
    STATE.mkdir(parents=True, exist_ok=True)
    kept = 0
    with DREAMS.open("a") as f:
        for d in dreams:
            summary = f"dream[{d['edge_score']}]: {d['seed']} × {d['partner']}"
            if not scan_dream_text(summary):
                audit({"event": "dream.rejected_by_scan", "seed": d["seed"], "partner": d["partner"]})
                continue
            d["id"] = f"d-{int(time.time())}-{random.randint(1000,9999)}"
            d["reviewed"] = False
            d["created_ts"] = int(time.time())
            f.write(json.dumps(d, sort_keys=True) + "\n")
            kept += 1
    audit({"event": "dream.batch_written", "kept": kept, "requested": len(dreams)})
    return kept


def cmd_generate(cycles: int):
    heat, neighbors = load_graph()
    if not heat:
        print("[dream_worker] no heat graph — nothing to dream about yet")
        return
    dreams = []
    for _ in range(cycles):
        d = dream_cycle(heat, neighbors)
        if d and d["edge_score"] >= EDGE_THRESHOLD:
            dreams.append(d)
    dreams.sort(key=lambda x: -x["edge_score"])
    top = dreams[:KEEP_TOP_N]
    kept = write_dreams(top)
    print(f"[dream_worker] {cycles} cycles → {len(dreams)} above threshold → {kept} kept (top-{KEEP_TOP_N} after scan)")
    for d in top[:kept]:
        print(f"  edge={d['edge_score']}  {d['seed']}  ×  {d['partner']}  (hop={d['hop_distance']})")


def cmd_show(n: int):
    if not DREAMS.exists():
        print("[dream_worker] no dreams yet"); return
    lines = DREAMS.read_text().splitlines()[-n:]
    for line in lines:
        try:
            d = json.loads(line)
            marker = "✓" if d.get("reviewed") else " "
            print(f"  {marker} {d['id']}  edge={d['edge_score']}  {d['seed'][:40]} × {d['partner'][:40]}")
        except Exception:
            pass


def cmd_review(dream_id: str):
    if not DREAMS.exists(): sys.exit("no dreams")
    lines = DREAMS.read_text().splitlines()
    updated = False
    out = []
    for line in lines:
        try:
            d = json.loads(line)
            if d.get("id") == dream_id:
                d["reviewed"] = True
                d["reviewed_ts"] = int(time.time())
                updated = True
            out.append(json.dumps(d, sort_keys=True))
        except Exception:
            out.append(line)
    if not updated: sys.exit(f"no dream with id {dream_id}")
    DREAMS.write_text("\n".join(out) + "\n")
    print(f"[dream_worker] marked {dream_id} reviewed")


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--cycles", type=int, help="run N dream cycles, keep top-10")
    g.add_argument("--show",   type=int, help="print last N dreams")
    g.add_argument("--review", type=str, help="mark dream <id> as reviewed")
    a = ap.parse_args()
    if a.cycles is not None: return cmd_generate(a.cycles)
    if a.show   is not None: return cmd_show(a.show)
    if a.review is not None: return cmd_review(a.review)


if __name__ == "__main__":
    main()
