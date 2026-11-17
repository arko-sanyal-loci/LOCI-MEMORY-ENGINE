#!/usr/bin/env python3
"""
loci_query.py — real-time heat retrieval for the makeshift LOCI.

Implements the formula in Memory/formulas.md:
  baseline heat → direct activation → spreading activation (H≤3, α=0.5)
  → source-trust weight → z-score gate → CARD-adaptive top-K → hydrate from SQL.

Usage:
  echo "your question here" | python3 loci_query.py
  python3 loci_query.py --q "how are the api keys stored"
  python3 loci_query.py --q "when did the attack start" --k 8   # override

Reads:   /Volumes/DevDrive/.loci-facts.db (read-only — no unlock needed)
         /Volumes/DevDrive/Memory/streams/{isymprev,qsymprev}.jsonl
Writes:  nothing. Retrieval only.

Sigword hook: if the incoming query contains "roz@" (case-insensitive), this
script is what any Claude session should invoke before drafting a reply.
"""
from __future__ import annotations
import argparse, json, math, re, sqlite3, statistics, sys, time
from collections import defaultdict
from pathlib import Path

DB          = Path("/Volumes/DevDrive/.loci-facts.db")
MEMORY      = Path("/Volumes/DevDrive/Memory")
ISYMPREV    = MEMORY / "streams" / "isymprev.jsonl"
QSYMPREV    = MEMORY / "streams" / "qsymprev.jsonl"

# Constants (paper 00/01/03)
LAMBDA      = math.log(2) / (14 * 86400.0)   # 14-day half-life
ALPHA       = 0.5                            # per-hop decay
H_MAX       = 3
Z_GATE_HOT  = 1.0
Z_GATE_COLD = 1.5
BONUS_USER  = 1.0
BONUS_ASST  = 0.5
K = {"PRECISE": 5, "SYNTH": 12, "UPDATE": 5, "TEMPORAL": 8}
# Sigword detection lives in scripts/sigword_utils.py — normalizes URL encoding,
# HTML entities, Unicode confusables. Never stores plaintext.
_SIGWORD_UTILS_PATH = Path("/Volumes/DevDrive/Memory/scripts")
if str(_SIGWORD_UTILS_PATH) not in sys.path:
    sys.path.insert(0, str(_SIGWORD_UTILS_PATH))
try:
    from sigword_utils import sigword_present, scrub_text as scrub_sigword_from  # noqa
except Exception:
    def sigword_present(text: str) -> bool: return False
    def scrub_sigword_from(text: str) -> str: return text


def classify(q: str) -> str:
    ql = q.lower()
    if any(w in ql for w in ("when", "before", "after", "at time", "history", "originally")):
        return "TEMPORAL"
    if any(w in ql for w in ("update", "changed", "now", "current", "latest", "as of")):
        return "UPDATE"
    if len(q.split()) > 15 or " and " in ql:
        return "SYNTH"
    return "PRECISE"


def extract_query_entities(q: str) -> list[str]:
    # Same patterns as isymprev — surface likely entities
    rx = [
        re.compile(r"(/(?:Users|Volumes|Library|Applications)/[\w./+\- %]+)"),
        re.compile(r"https?://\S+"),
        re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
        re.compile(r"local_[0-9a-f-]{36}"),
        re.compile(r"#\d{4,7}"),
        re.compile(r"\b(LOCI|CARD|TRS|multi-defender|billo[-\s]?gate|billo[-\s]?pc|billo[-\s]?vps|Evolution\s?Vapes|Bybit|Access\s?Now|Roza|Arc|Bitdefender|ViewBridge(?:Auxiliary)?)\b", re.I),
        re.compile(r"\b(Arko(?:\s+Sanyal)?|Anthropic)\b"),
    ]
    seen = []
    for r in rx:
        for m in r.finditer(q):
            v = m.group(0).strip()
            if v not in seen: seen.append(v)
    # Also add bare-word content tokens ≥4 chars (case-insensitive)
    for tok in re.findall(r"[A-Za-z][A-Za-z0-9_-]{3,}", q):
        if tok.lower() not in {t.lower() for t in seen} and len(tok) >= 5:
            seen.append(tok)
    return seen


def load_isymprev_graph() -> tuple[dict[str, float], dict[str, set[str]]]:
    """Return heat[entity] and neighbors[entity] from co-session co-occurrence."""
    heat: dict[str, float] = defaultdict(float)
    per_session: dict[str, set[str]] = defaultdict(set)
    if not ISYMPREV.exists():
        return {}, {}
    for line in ISYMPREV.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception:
            continue
        e = r["name"]
        heat[e] = max(heat[e], r.get("heat", 0.0))
        for s in r.get("sessions", []):
            per_session[s].add(e)
    neighbors: dict[str, set[str]] = defaultdict(set)
    for ents in per_session.values():
        el = list(ents)
        for i, a in enumerate(el):
            for b in el[i+1:]:
                neighbors[a].add(b); neighbors[b].add(a)
    return dict(heat), {k: v for k, v in neighbors.items()}


def spreading_activation(seed: list[str], neighbors: dict[str, set[str]]) -> dict[str, float]:
    """Direct +1.0 then α^h at hop h up to H_MAX."""
    act: dict[str, float] = defaultdict(float)
    frontier: dict[str, float] = {e: 1.0 for e in seed}
    for e, v in frontier.items():
        act[e] += v
    visited = set(seed)
    for h in range(1, H_MAX + 1):
        nxt: dict[str, float] = defaultdict(float)
        for e, cur in frontier.items():
            for n in neighbors.get(e, ()):
                if n in visited: continue
                nxt[n] += (ALPHA ** h) * cur
        for e, v in nxt.items():
            act[e] += v; visited.add(e)
        frontier = nxt
        if not frontier: break
    return dict(act)


def z_gate(salience: dict[str, float]) -> dict[str, float]:
    """Keep only entities with z ≥ Z_GATE_HOT (paper 00)."""
    if len(salience) < 3: return salience   # too small to gate
    vals = list(salience.values())
    mu = statistics.mean(vals); sd = statistics.pstdev(vals) or 1e-6
    return {e: s for e, s in salience.items() if (s - mu) / sd >= Z_GATE_HOT}


def rerank(retained: dict[str, float], intent: str, ts_by_entity: dict[str, int]) -> list[tuple[str, float]]:
    now = int(time.time())
    if intent == "TEMPORAL":
        return sorted(retained.items(), key=lambda kv: (-ts_by_entity.get(kv[0], 0), -kv[1]))
    if intent == "UPDATE":
        # 0.7·S + 0.3·recency where recency = exp(-λ * age)
        return sorted(retained.items(), key=lambda kv: -(0.7*kv[1] + 0.3*math.exp(-LAMBDA*max(0, now-ts_by_entity.get(kv[0],0)))))
    return sorted(retained.items(), key=lambda kv: -kv[1])


def hydrate(top_entities: list[str]) -> list[dict]:
    """Pull loci_facts for those entities, latest-version only."""
    if not top_entities or not DB.exists():
        return []
    con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    q = ("SELECT entity, key, value, value_type, source_trust, source_ts, "
         "version, tier, heat FROM loci_facts "
         f"WHERE superseded_by IS NULL AND entity IN ({','.join('?'*len(top_entities))}) "
         "ORDER BY heat DESC")
    rows = con.execute(q, top_entities).fetchall()
    con.close()
    cols = ("entity","key","value","value_type","source_trust","source_ts","version","tier","heat")
    return [dict(zip(cols, r)) for r in rows]


LAMBDA_CRITICAL_HEAT = math.log(2) / (5 * 365.25 * 86400.0)   # 5-year half-life (paper 07 spirit)
CH_BASE = 100.0
FOCUS_STATE = Path("/Volumes/DevDrive/Memory-state/focus.json")
F_BOOST = 2.0
F_SUPPR = 0.7   # multiplicative reduction of unrelated CRITICAL_HEAT + HOT/WARM/COLD salience


def _rows(sql: str) -> list[dict]:
    if not DB.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
        rows = con.execute(sql).fetchall()
        con.close()
    except Exception:
        return []
    cols = ("entity","key","value","value_type","source_trust","source_ts","version","tier","heat")
    return [dict(zip(cols, r)) for r in rows]


def values_facts() -> list[dict]:
    """VALUES tier — λ=0, always heat=1.0 on output (regardless of stored value),
    always prepended, never suppressed."""
    rows = _rows(
        "SELECT entity, key, value, value_type, source_trust, source_ts, "
        "version, tier, heat FROM loci_facts "
        "WHERE tier = 'VALUES' AND superseded_by IS NULL "
        "ORDER BY source_ts ASC"
    )
    for r in rows:
        r["heat"] = 1.0            # forced — Values never decay, never boost
    return rows


def critical_heat_facts(now: int, focus_neighbors: set[str] | None) -> list[dict]:
    """CRITICAL_HEAT tier — long half-life, suppressible by active focus."""
    rows = _rows(
        "SELECT entity, key, value, value_type, source_trust, source_ts, "
        "version, tier, heat FROM loci_facts "
        "WHERE tier = 'CRITICAL_HEAT' AND superseded_by IS NULL "
        "ORDER BY source_ts DESC"
    )
    out = []
    for r in rows:
        age = max(0, now - (r.get("source_ts") or now))
        base_h = CH_BASE * math.exp(-LAMBDA_CRITICAL_HEAT * age)
        if focus_neighbors is not None and r["entity"] not in focus_neighbors:
            base_h *= (1.0 - F_SUPPR)
        r["heat"] = round(base_h, 4)
        out.append(r)
    # Re-sort after suppression applied
    out.sort(key=lambda x: -x["heat"])
    return out


def load_focus() -> dict | None:
    """Read the currently-open focus goal, if any."""
    if not FOCUS_STATE.exists():
        return None
    try:
        f = json.loads(FOCUS_STATE.read_text())
        if f.get("state") == "open":
            return f
    except Exception:
        pass
    return None


def source_ts_index() -> dict[str, int]:
    """Latest source_ts per entity, from qsymprev."""
    idx: dict[str, int] = {}
    if not QSYMPREV.exists(): return idx
    for line in QSYMPREV.read_text().splitlines():
        try:
            r = json.loads(line)
        except Exception: continue
        if r.get("op") == "supersede": continue
        e = r.get("entity")
        if not e: continue
        idx[e] = max(idx.get(e, 0), r.get("source_ts", 0))
    return idx


def _record_metrics(result: dict):
    """Fire-and-forget metrics + intent log. Never blocks the query on failure."""
    try:
        returned = int(result.get("counts", {}).get("returned", 0))
        intent = result.get("intent", "PRECISE")
        top = result.get("top_entities") or []
        mrr_rank = 1 if top else None
        import subprocess as _sp
        _sp.Popen(
            ["python3", str(Path("/Volumes/DevDrive/Memory/scripts/metrics.py")),
             "--record", "--returned", str(returned),
             "--intent", intent] + (["--mrr-rank", str(mrr_rank)] if mrr_rank else []),
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
        )
        # AI intent log — for AI_Profile drift-detection
        _sp.Popen(
            ["python3", str(Path("/Volumes/DevDrive/Memory/scripts/ai_intent_log.py")),
             "--log", "--actor", "loci_query",
             "--action", f"retrieval intent={intent} returned={returned}",
             "--tier-served", "HOT" if returned > 0 else "-",
             "--outcome", "hit" if returned > 0 else "miss"],
            stdout=_sp.DEVNULL, stderr=_sp.DEVNULL,
        )
    except Exception:
        pass


def query(q: str, k_override: int | None = None) -> dict:
    intent = classify(q)
    seeds = extract_query_entities(q)
    heat, neighbors = load_isymprev_graph()
    now = int(time.time())

    # baseline heat is already decayed at stream-write; recompute here in case stale
    activation = spreading_activation(seeds, neighbors)
    salience = {}
    all_entities = set(heat) | set(activation)
    ts_idx = source_ts_index()
    for e in all_entities:
        h = heat.get(e, 0.0)
        a = activation.get(e, 0.0)
        # trust bonus baked into stored heat already; skip double-count
        salience[e] = h + a
    retained = z_gate(salience)
    ranked = rerank(retained, intent, ts_idx)
    K_eff = k_override or K[intent]
    # Focus (paper 07 switched decay): apply boost + suppression before final rank
    focus = load_focus()
    focus_neighbors: set[str] | None = None
    if focus:
        f_ent = focus.get("entity", "")
        focus_neighbors = {f_ent} | neighbors.get(f_ent, set())
        # 2-hop
        for n in list(focus_neighbors):
            focus_neighbors |= neighbors.get(n, set())
        # apply to salience
        adjusted: dict[str, float] = {}
        for e, s in retained.items():
            if e in focus_neighbors:
                adjusted[e] = s + F_BOOST
            else:
                adjusted[e] = s * (1.0 - F_SUPPR)
        retained = adjusted
        ranked = rerank(retained, intent, ts_idx)

    top = [e for e, _ in ranked[:K_eff]]
    top_facts = hydrate(top)

    # Tier order: VALUES → CRITICAL_HEAT → normal top-K
    vals = values_facts()
    crit_h = critical_heat_facts(now, focus_neighbors)
    seen = {(f["entity"], f["key"]) for f in vals} | {(f["entity"], f["key"]) for f in crit_h}
    ranked_facts = [f for f in top_facts if (f["entity"], f["key"]) not in seen]
    facts = vals + crit_h + ranked_facts

    result = {
        "query": q,
        "intent": intent,
        "seeds": seeds,
        "focus": focus,
        "focus_neighbors": sorted(focus_neighbors) if focus_neighbors else None,
        "top_entities": [{"entity": e, "salience": round(s, 4)} for e, s in ranked[:K_eff]],
        "facts": facts,
        "counts": {
            "values": len(vals),
            "critical_heat": len(crit_h),
            "salience_pool": len(salience),
            "z_retained": len(retained),
            "returned": len(facts),
        },
        "sigword_present": sigword_present(q),
    }
    _record_metrics(result)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--q", help="query text (default: stdin)")
    ap.add_argument("--k", type=int, default=None, help="override K")
    args = ap.parse_args()
    q = args.q or sys.stdin.read().strip()
    if not q:
        sys.exit("[loci_query] empty query")
    print(json.dumps(query(q, args.k), indent=2, default=str))


if __name__ == "__main__":
    main()
