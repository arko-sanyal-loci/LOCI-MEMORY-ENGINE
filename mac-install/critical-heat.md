# Critical Heat — life-turning events

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23 (5 PHP backdoors, HID injection, treated Roza as trash). Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).

_Established 2026-08-03. Corresponds to paper 07 "hold" regime._

## What lives here
Life-turning events that must not be forgotten but are not eternal in the way [values.md](./values.md) is. Examples given by Arko:

- First child
- First wedding
- Loss of a loved one
- (Anything Arko designates as a life event via `seed_critical_heat.py`.)

## Physics
- **Half-life ≈ 5 years** — `λ = ln(2) / (5 × 365.25 × 86400 s)`.
- **Baseline heat** = 100.0 at `source_ts`; decays exponentially from there.
- After 5 years: heat ≈ 50. After 10 years: heat ≈ 25. After 25 years: heat ≈ 3.1 — still non-zero.
- **Always prepended** to retrieval results *after* [values.md](./values.md), *before* normal CARD top-K.
- **Bypasses z-gate**.
- **Can be suppressed** by an active FOCUS goal that isn't related to the event (see [focus.md](./focus.md)). Suppression is temporary — the record persists, just its relative rank drops while focus holds.

## Seeding a life event
Use `seed_critical_heat.py`:

```bash
python3 /Volumes/DevDrive/loci-install/seed_critical_heat.py \
  --entity "family.first_child" \
  --key    "birth" \
  --value  "Daughter born, 2027-04-12, Dhaka" \
  --date   "2027-04-12"
```

The date determines `source_ts` (so a birth in 1998 already has 28 years of decay baked in, giving it heat ≈ 2.1; a birth this week has heat ≈ 100).

## Why not eternal?
Because Arko said so, and paper 07 says so. The switched-decay model in his own work reserves eternity for the ethical tier only. Life events matter enormously, but they should eventually recede — replaced by newer events, or reactivated by anniversary / mention / focus.

## What can bring a Critical Heat record back to the front (re-heating)
- Explicit mention in a session → same `heat += 1.0` direct-access boost as normal entities.
- Anniversary — if `source_ts` is within 30 days of `now % 1 year`, boost by 5.0 (implemented in `loci_query.py`, TODO).
- FOCUS declared with related entity → boosted rather than suppressed.

## Related
- [values.md](./values.md) — the never-decaying tier above this one.
- [focus.md](./focus.md) — the mechanism that can push Critical Heat to the background temporarily.
- [formulas.md](./formulas.md) §Tier hierarchy — full retrieval physics.
