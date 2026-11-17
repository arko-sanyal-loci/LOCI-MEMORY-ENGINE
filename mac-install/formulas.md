# Heat-retrieval formulas — bringing relevant `loci_facts` up in real time

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23 (5 PHP backdoors, HID injection, treated Roza as trash). Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).

_Grounded in paper 00 (TRS), paper 01 (LOCI ∞), paper 03 (CARD). Reference implementation: `Memory/extractors/loci_query.py`._

## The problem
As Arko is talking (typing a message, running a command, or the LLM is drafting a reply), we want the **top-K most relevant** `loci_facts` rows to bubble to the top **automatically**, ranked by a composite salience that fuses:

- **Stored heat** (how much the entity has been talked about lately, per paper 01 decay).
- **Query activation** (how much the current message excites the entity, per paper 00 spreading activation).
- **Source trust** (per paper 02 source-trust weighting).
- **Recency** (per paper 03 CARD's KU-mode reranking).

Then gate by **z-score** (paper 00) and slice with **CARD-adaptive K** (paper 03).

---

## Tier hierarchy (retrieval priority, top → bottom)

| Tier | λ (decay rate) | Half-life | Suppressible by FOCUS? | Notes |
|---|---|---|---|---|
| **VALUES** | `0` | ∞ | **No** | Eternal ethical/behavioral commitments. See [values.md](./values.md). |
| **CRITICAL_HEAT** | `ln(2) / 5 years` | ~5 years | Yes — see FOCUS below | Life-turning events. See [critical-heat.md](./critical-heat.md). |
| **FOCUS (active)** | `ln(2) / 30 days` (hold) → `ln(2) / 1 hour` (release, paper 07) | ~30 days while open | — (this IS the suppressor) | Currently-open long-term goal. See [focus.md](./focus.md). |
| **STRATEGIES** | opaque (encrypted at rest, not decayed in retrieval — activation-gated) | — | — | AES-128 Fernet, PBKDF2-HMAC-SHA256, sigword + book. See [strategies.md](./strategies.md). |
| **ARSENAL** | `ln(2) / 14 days` | 14 days | Yes — boosted if focus-related | Capabilities / tools / methods. See [arsenal.md](./arsenal.md). |
| HOT / WARM / COLD | `ln(2) / 14 days` | 14 days | Yes — deprioritized while focus active | Standard paper 01 tiering. |
| **ETHICS_CAPPED** | `ln(2) / 24 h` (fast) | 24 hours | — (cannot be boosted; cap is absolute) | Hard `heat ≤ 0.1`, retrieval `K = 1` (summary only), never crystallizes, never enters STRATEGIES / ARSENAL / VALUES / CRITICAL_HEAT. See [learning-loop.md](./learning-loop.md) §Ethics gate. |

### VALUES — physics
```
tier(e) = VALUES ⇒ λ = 0
                   heat(e) = 1e9   (sentinel — always max)
                   superseded_by is always NULL  (immutable; new values append as V3, V4…)
                   z-gate does NOT apply
                   FOCUS cannot suppress
                   always prepended to every retrieval, regardless of intent or K
```

### CRITICAL_HEAT — physics
```
tier(e) = CRITICAL_HEAT ⇒ λ_ch = ln(2) / (5 years)
                          heat(e) = base × exp(−λ_ch × (t_now − event_ts))
                          base = 100.0  (dominates normal HOT for many years)
                          FOCUS can push to background via focus_suppression(e)
                          always prepended AFTER VALUES, before normal top-K
                          bypasses z-gate
```
Life events *do* fade — but on a scale of years, not weeks.

### FOCUS — the switched-decay regime (paper 07)
When Arko declares an open focus goal (via `set_focus.py`), a `focus_active` record is written to `Memory-state/focus.json`. While it holds:

```
For every candidate fact e with tier ≠ VALUES:
  focus_boost(e)       = F_BOOST  if e ∈ neighbors(focus.entity, hops≤2) else 0
                       = 2.0 default
  focus_suppression(e) = SUPPR    if e ∉ neighbors and tier ∈ {CRITICAL_HEAT, HOT, WARM, COLD} else 0
                       = 0.7 default (multiplicative reduction of salience)

S_focused(e) = ( S(e) + focus_boost(e) ) × ( 1 − focus_suppression(e) )
```

On focus **resolution** (fulfilled | re-clamped | relinquished | nullified | abandoned — paper 07 release taxonomy):
- λ_focus switches from `hold` (~30 d) to `release` (~1 h) — trace collapses fast.
- CRITICAL_HEAT + normal tiers return to their un-suppressed salience.
- The focus record is archived with its resolution mode.

### Retrieval order becomes
```
result =  VALUES_facts                              (λ=0, always)
       ++ CRITICAL_HEAT_facts (with focus_suppression applied)
       ++ top_K_by_CARD(S_focused, intent)          (with focus_boost applied)
       (deduped by (entity, key); higher-tier wins on ties)
```

**Marking as VALUES or CRITICAL_HEAT** requires a signed patch from `signer = loci_facts` with the correct `tier` in the SQL params. VALUES also require `superseded_by IS NULL` always (never overwritten).

## Constants
| Symbol | Meaning | Value |
|---|---|---|
| `λ` | Passive decay rate | `ln(2) / (14 d) = 5.7269 × 10⁻⁷ s⁻¹` (14-day half-life, paper 01) |
| `α` | Per-hop spreading-activation decay | `0.5` (paper 01: direct +1.0 → 3-hop +0.125 ≈ 0.5³) |
| `H_max` | Max propagation hops | `3` (paper 00: "spreading activation over two hops" → we use 3 to cover paper 01's 3-hop figure) |
| `z_gate` | z-score gate threshold | `1.0` for HOT/WARM, `1.5` for COLD (paper 00 §z-score gate) |
| `bonus_user` | Source-trust bonus (user-stated) | `1.0` (paper 02) |
| `bonus_asst` | Source-trust bonus (assistant-inferred) | `0.5` (paper 02) |
| `K_precise` | CARD top-K for precise lookup | `5` (paper 03: 3–5) |
| `K_synth` | CARD top-K for multi-hop synthesis | `12` (paper 03: 10–15) |
| `K_update` | CARD top-K for knowledge update | `5` with recency rerank (paper 03) |
| `K_temporal` | CARD top-K for temporal reasoning | `8` (paper 03: 7–10, timestamp-ordered) |

---

## Formula (canonical form)

**Step 1 — Baseline heat** for every stored entity `e` at query time `t_now`:
```
heat(e) = mentions(e) × exp( −λ × (t_now − last_ts(e)) )
```

**Step 2 — Direct activation** for entities `e_i` mentioned in the current turn `q`:
```
act_direct(e_i) = 1.0                                        (paper 01: "Direct access: heat += 1.0")
```

**Step 3 — Spreading activation** across the co-occurrence graph, hops `h = 1..H_max`:
```
act(e) = Σ over source e_i ∈ q, hops h:
           α^h × w(edge from e_i to e at hop h)
```
where `w(edge)` = normalized co-occurrence weight from the isymprev stream.

**Step 4 — Composite salience** (with source-trust weight and version-latest filter):
```
S(e) = ( heat(e) + act_direct(e) + act(e) )
       × ( 1 + bonus_source_trust(e) )
       × latest_version_indicator(e)
```
where `latest_version_indicator(e) = 1` if the record is the current version chain head (paper 02), else `0`.

**Step 5 — z-score gate** per entity type `τ = type(e)`:
```
z(e) = ( S(e) − μ_τ ) / σ_τ         (μ_τ, σ_τ computed over the entire type population)
retain e iff z(e) ≥ z_gate           (paper 00 z-score gate suppresses low-confidence)
```

**Step 6 — CARD top-K slice** based on classified query intent:
```
intent = classify(q) ∈ { PRECISE, SYNTH, UPDATE, TEMPORAL }
K      = { PRECISE: K_precise, SYNTH: K_synth, UPDATE: K_update, TEMPORAL: K_temporal }[intent]

rank retained entities by:
  intent = PRECISE   → S(e) desc
  intent = SYNTH     → S(e) desc
  intent = UPDATE    → 0.7·S(e) + 0.3·recency(e)   (recency-weighted rerank)
  intent = TEMPORAL  → source_ts(e) desc, then S(e)

return top-K
```

**Step 7 — Hydrate** each retained entity via SQL JOIN on `.loci-facts.db`:
```sql
SELECT entity, key, value, value_type, source_trust, source_ts, version, tier, heat
FROM   loci_facts
WHERE  entity IN (:top_k_entity_names)
  AND  superseded_by IS NULL           -- version-latest filter (paper 02)
ORDER  BY heat DESC;
```

---

## Complexity
- Baseline heat: `O(|entities in query|)` at read time (heat is stored, only re-evaluated for candidates).
- Spreading activation: `O(k × d^H)` where `k` = query entities, `d` = avg neighbor fan-out, `H` = 3. For Arko's DB (~5K entities), stays under 5 ms.
- z-gate: `O(|candidates|)`.
- Total: **~1 ms for HOT-tier hits, ~5 ms warm, ~50 ms cold** (paper 01 tier latencies).

---

## Query intent classifier (minimal)
```python
def classify(q: str) -> str:
    ql = q.lower()
    if any(w in ql for w in ("when", "before", "after", "at time", "history")):
        return "TEMPORAL"
    if any(w in ql for w in ("update", "changed", "now", "current", "latest")):
        return "UPDATE"
    if len(q.split()) > 15 or "and" in ql.split():
        return "SYNTH"
    return "PRECISE"
```

---

## Sigword hook
When Arko's message contains **`[SIGWORD — hash-verified, per V3]`** (see [signature.md](./signature.md)), the session runs this retrieval before drafting the reply, and cites the returned facts inline. Reference implementation: `Memory/extractors/loci_query.py`.

## Falsification / stop rule
If retrieval returns **zero** facts above the z-gate for a query where Arko says the answer should be in memory, **do not fabricate** — surface: "no fact in LOCI above z=1.0 for [query terms]; recent sessions to check: [top 3 sessions from isymprev]".
