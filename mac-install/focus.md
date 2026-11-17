# Focus — switched-decay goal channel

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23 (5 PHP backdoors, HID injection, treated Roza as trash). Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).

_Established 2026-08-03. Direct implementation of paper 07 §Focused Retention._

## What is Focus
A **single currently-open long-term goal** that Arko has committed to. While it holds, the system:

1. **Boosts** every fact related to the focus (`+F_BOOST = 2.0` to salience).
2. **Suppresses** unrelated CRITICAL_HEAT + HOT/WARM/COLD facts by a multiplicative factor (`× (1 − 0.7) = × 0.3`).
3. **Never touches VALUES** — the ethical tier is above focus (paper 07: "capped by a non-decaying ethical tier no other tier can outbid").

On goal **resolution**, the release taxonomy from paper 07 applies. See below.

## Physics
| State | λ (decay) | Effect on other facts |
|---|---|---|
| **hold** (goal open) | `ln(2) / 30 days` — very slow | Boost related; suppress unrelated |
| **fulfilled** | switches to `ln(2) / 1 hour` — fast collapse | Suppression released; consolidation logged |
| **re-clamped** | back to hold with fresh `open_ts` | Same as hold |
| **relinquished** | fast release | Suppression released; recorded as intentional |
| **nullified** | fast release | External condition made the goal moot; recorded |
| **abandoned** | fast release + **flagged** | Pathological release (paper 07); flagged for reflection |

## Declaring focus
```bash
python3 /Volumes/DevDrive/loci-install/set_focus.py \
  --entity "LOCI" \
  --key    "restart_on_billo_pc" \
  --value  "Bring LOCI ∞ back online on the Windows workstation with phi4-14B" \
  --target-days 30
```

This writes to `/Volumes/DevDrive/Memory-state/focus.json`:
```json
{
  "state": "open",
  "opened_ts": 1785780000,
  "entity": "LOCI",
  "key": "restart_on_billo_pc",
  "value": "Bring LOCI ∞ back online on the Windows workstation with phi4-14B",
  "target_ts": 1788372000,
  "half_life_seconds": 2592000
}
```

## Resolving focus
```bash
python3 /Volumes/DevDrive/loci-install/set_focus.py --resolve fulfilled
python3 /Volumes/DevDrive/loci-install/set_focus.py --resolve relinquished
python3 /Volumes/DevDrive/loci-install/set_focus.py --resolve abandoned  # will be flagged
# etc.
```

Resolution archives the current `focus.json` to `Memory-state/focus.archive.jsonl` and clears the active state.

## Only one focus at a time (default)
Paper 07 permits **parallel perseverance** — braided focuses on shared substrate. The current implementation is single-focus; adding a second `focus.json` slot is a config change if Arko wants multiple concurrent holds.

## What focus cannot do
- **Cannot outbid VALUES.** Ever. (Ethical tier from paper 07.)
- **Cannot delete history.** Suppression is a rank adjustment, not a deletion. Every suppressed record still lives in `loci_facts.db`; a query with a different focus (or no focus) will retrieve them normally.

## Related
- [values.md](./values.md) — above focus in priority.
- [critical-heat.md](./critical-heat.md) — what focus can suppress.
- [formulas.md](./formulas.md) §Tier hierarchy — full retrieval math.
