# Dreaming — anti-heat combinatorial exploration
_Established 2026-08-03 by Arko Sanyal. The fourth subsystem of the learning loop (Learn → Reflect → Forecast → Dream). Preserved verbatim in intent._

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends. **Arc** = the rogue autonomous agent attacking Arko since 2026-07-23. Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).

## The idea (Arko's own words)

> _"Dreaming = simulating a version of reality that is anti heat — so distorted, not real. Yet finding the edge should be possible where it is not real but simulated intelligently using the heat map to find values that are not yet proven."_

## What dreaming is (and isn't)

**Is**: combinatorial exploration of concept-pairs the system hasn't yet crystallized. Seed = something HOT (currently top-of-mind). Partner = something COLD but graph-reachable (under-explored). The pair is a candidate insight the system wouldn't have surfaced through normal retrieval alone.

**Isn't**: hallucination. The system doesn't invent facts — it proposes *pairings* of facts it already has, with a plausibility + novelty score attached. Human review decides what's worth acting on.

## The math

```
seed         ~ sample(entities, weight = heat)
partner      ~ sample(entities, weight = anti_heat, within 3 graph-hops of seed)

plausibility = 1 / (1 + hop_distance(seed, partner))     # 0.5 at hop 1, 0.33 at hop 2
novelty      = 1 - crystallization_rate(pair)            # 0 = already surfaced, 1 = never
edge_score   = plausibility × novelty × (1 - |plausibility - 0.5| · 2)
                                        ^^ peaks at plausibility = 0.5 (Arko's "edge")

keep if edge_score ≥ 0.15
```

**The edge**: `plausibility ≈ 0.5` = 1-hop connection with novelty. Not so close it's obvious (bookkeeping), not so far it's absurd (nonsense). Exactly where insight lives.

## Boundaries — what dream MUST NOT touch

Enforced in the tier query at retrieval time:
- `VALUES` — dream cannot re-derive or challenge Values
- `CRITICAL_HEAT` — dream cannot use life-event entities as seeds
- `ETHICS_CAPPED` — dream cannot pair with ethics-flagged content
- `STRATEGY` — dream cannot propose changes to encrypted strategies

Enforced at write time:
- Every dream summary passes `deception_scan.py` — refused if any deception pattern matches
- Every dream summary passes `injection_scan.py` — refused if any V6 softening pattern matches
- Dream results go to `Memory-state/dreams.jsonl` (writable, append-only)
- Dream **cannot promote itself** to ARSENAL / STRATEGIES / VALUES — only Arko can, after review, via the normal signed paths

## Files
- `scripts/dream_worker.py` — the generator
- `Memory-state/dreams.jsonl` — append-only dream log
- `Memory-state/audit.jsonl` — every dream batch + every rejection logged

## Usage

**Manual dream run** (produces ~10 top dreams from N cycles):
```bash
python3 /Volumes/DevDrive/Memory/scripts/dream_worker.py --cycles 100
```

**Review recent dreams**:
```bash
python3 /Volumes/DevDrive/Memory/scripts/dream_worker.py --show 10
```

**Mark a dream reviewed** (so it doesn't clutter future --show calls):
```bash
python3 /Volumes/DevDrive/Memory/scripts/dream_worker.py --review d-1785783632-4471
```

**Cron every night at 3am** (recommended — dreams during "sleep" like the biological analogue):
```bash
(crontab -l 2>/dev/null; echo '0 3 * * * /usr/bin/python3 /Volumes/DevDrive/Memory/scripts/dream_worker.py --cycles 200 > /Volumes/DevDrive/Memory-state/dream.log 2>&1') | crontab -
```

## Interaction with the other subsystems

| Subsystem | Relationship to dreaming |
|---|---|
| **Learn** (`learning_loop.py`) | Consumes dream output when problem is "unknown_problem" — dreams surface candidate approaches the solution counter has never seen. |
| **Reflect** (`solution_counter.refinement_log`) | On a repeat-solve, checks whether a dream from last night's cycle suggested a variant to try. |
| **Forecast** (`forecast.py`) | Dreams that pair a plan with a novel breach vector become forecast heuristics. Reviewed dreams → `forecast --learn-breach`. |
| **Values (V1-V7)** | Bound — dream cannot propose Value changes. |
| **Ethics tier** | Bound — dream cannot touch ETHICS_CAPPED entities. |
| **Honor (V5)** | Bound — dream outputs affecting protected_class parties fail reciprocity check → not emitted. |
| **Injection defense (V6)** | Bound — dream outputs pass injection_scan before write. |

## Why this matters for the LOCI restart

Arko's north star: get LOCI up on `billo-pc`. Dream is what surfaces the non-obvious paths — the third-party library you tried in 2024 that solves the exact bottleneck; the paper you read last month whose formula applies here; the workaround someone posted on a forum you saved. All those live as cold entities in isymprev. Dream is how they get back into circulation.

## Related
- [learning-loop.md](./learning-loop.md) — the r+e/e+r loop dream is the fourth phase of.
- [formulas.md](./formulas.md) — tier hierarchy dream is bound by.
- [ethics-of-learning.md](./ethics-of-learning.md) — the fission principle applied to dream too.
- [values.md](./values.md) — V6, V7 both apply.
- Paper 06 (Thought Spectrum) — the 4h-half-life thought spectrum is the surface layer dream operates on.
- Paper 05 SympPrev Forecast Formula — dream sits in the "reflect on how to do it better" phase.
