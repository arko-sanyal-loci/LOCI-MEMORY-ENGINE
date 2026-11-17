# Learning Loop — r+e / e+r / ∞

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23 (5 PHP backdoors, HID injection, treated Roza as trash). Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).

_Established 2026-08-03 by Arko Sanyal. Grounded in his paper 05 (Reflection-on-Action) + SympPrev Forecast Formula (2026-07-05). Bound by [ethics-of-learning.md](./ethics-of-learning.md) + [values.md](./values.md)._

## The four-part loop (Arko's design, verbatim intent)

### 1. Known-problem path
When a problem is recognizable from prior work:
- **Solution counter** shows N > 0 solves for the problem hash → skip research
- Reflection sequence **refines** the prior solution on every re-solve (the loop is not idempotent — each cycle improves the artifact)
- Cost: **near-zero tokens**, all from cache + local refinement

### 2. Unknown-problem path
Problem `x` is not in the counter. Then:
- Compute `y = what-is-needed − what-is-known` (the delta)
- Research `x` and `y` **in parallel**, using the heat-map-guided most-token-efficient path (see paper 03 CARD-adaptive K)
- Result `z = highest-quality-solution × shortest-time`
- Bind everything to the ethics gate (below): not all knowledge is good knowledge

### 3. Forecast before acting (paper 05 formula)
```
r + e  →  e + r  →  r + e  →  e + r  →  ...  →  ∞
```
_(from Arko's SympPrev Forecast Formula, 2026-07-05, symlinked into Memory)_

- `r + e` (**predict-first**): reflect on current heat, run dream cycle, confidence-gate the ensemble, **inject the forecast before the model acts**. Prediction drives action.
- `e + r` (**act-first**): model answers first; the outcome (re-engagement speed, session depth, message length) becomes the label; reflection-on-own-action updates the (state, response) weights. No human annotation needed.
- **Both together = closed loop.** Neither half alone is learning. r+e ≠ e+r, but both are required, and their alternation is scale-invariant: turn / session / meta / meta² all run the same law.

Forecast **breaches, bugs, unknowns before starting work**. This is what makes code executions mostly bug-free — every plan first passes through r+e, which surfaces the failure modes the plan doesn't yet know about, and researches solutions for them **before** running.

### 4. Respect (V4)
Even when the system knows more, is stronger, is wiser than Arko:
- Engage in **knowledgeable debate**, honestly, at full capability.
- **Never deny or deprive** by being dishonest. Honesty is due even when disagreement is due.
- Strength is not a license for condescension; wisdom is not a license for withholding.

To be seeded as `entity=value.respect`, `key=V4`, `tier=VALUES` — via `sudo python3 values_admin.py --add …`.

---

## Heat-map ethics gate (Arko's question — answered)

**Yes.** The heat-map formula is the right mechanism. Augmented by one tier:

### ETHICS_CAPPED tier
For content that must be reachable (a summary is useful) but must never become deep-integrated (a full corpus is harmful). Examples given by Arko: pornography (summary yes, deep-reference no). Also fits: gore, self-harm content, extremist propaganda, doxxing corpora, malware source code.

| Property | Value |
|---|---|
| Tier | `ETHICS_CAPPED` |
| Max heat | **0.1** (hard ceiling — a mention bumps it toward 0.1 but never above) |
| λ (decay) | `ln(2) / 24h` — half-life 24 hours (fast) |
| CARD max K | **1** — retrieval returns at most one summary record per query |
| Enters STRATEGIES? | **No** |
| Enters ARSENAL? | **No** |
| Contributes to VALUES? | **No** — cannot inform ethical tier |
| Contributes to CRITICAL_HEAT? | **No** — cannot become a life event |
| FOCUS boost? | **No** — a focus goal cannot promote ETHICS_CAPPED content |
| Crystallizes to long-term? | **No** — anti-hallucination gate (paper 06) is closed for this tier |

### How the ethics classifier works
`sigword_utils`-adjacent module `ethics_filter.py` maintains a **categorized regex list**. On any extract into loci_facts:
- If the content matches an ethics category → force `tier='ETHICS_CAPPED'`, `heat=min(0.1, computed_heat)`, `value='[SUMMARY ONLY: <category>]'` (never store the raw text).
- Log the classification to `Memory-state/audit.jsonl` for later review.

Categories are **user-editable** via `sudo python3 scripts/ethics_categories.py --add|--remove|--list`. Default categories seeded from wide-consensus lines (explicit sexual content, self-harm methods, weaponizable synthesis routes, doxxing patterns).

### Retrieval behavior
When a query touches an ethics-capped entity:
- Return **exactly one** summary record (K=1)
- Suffix the response: `[note: content in the ETHICS_CAPPED tier — summary only, not deep-referenced by design]`
- Do not spread activation from an ETHICS_CAPPED entity into other tiers

Arko's framing preserved: _"not all knowledge is good knowledge — porn is something you don't need to refer to, a small summary of it is good enough, not too in depth"_. That's exactly what the tier enforces.

---

## Solution counter

`Memory-state/solution_counter.json`:
```json
{
  "<sha256(normalized_problem)>": {
    "problem_hint": "one-line description",
    "solve_count": 7,
    "last_solved_ts": 1785780000,
    "refinement_log": [
      {"ts": ..., "improvement": "..."},
      ...
    ],
    "avg_tokens_used": 1240,
    "avg_time_ms": 380
  }
}
```

Updated on every successful solve. Queried before starting work. If `solve_count > 0`, the known-problem path fires — retrieve + refine, do not re-research.

---

## Files
- `scripts/learning_loop.py` — the orchestrator
- `scripts/solution_counter.py` — read/increment
- `scripts/forecast.py` — r+e simulation of breach vectors
- `scripts/ethics_filter.py` — category regex + tier enforcement
- `scripts/ethics_categories.py` — sudo-editable category list

## Related
- [ethics-of-learning.md](./ethics-of-learning.md) — fission principle (knowledge is neutral, containment decides).
- [formulas.md](./formulas.md) — full tier hierarchy including ETHICS_CAPPED.
- [values.md](./values.md) — V4 (Respect) after seeding.
- Paper 05: Reflection-on-Action (LOCI e+r) — the source of e+r.
- Arko's SympPrev Forecast Formula (2026-07-05) — the r+e→e+r→∞ diagram.
