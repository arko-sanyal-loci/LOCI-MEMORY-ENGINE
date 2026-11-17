# Arsenal — tier=ARSENAL

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23 (5 PHP backdoors, HID injection, treated Roza as trash). Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).

_Established 2026-08-03._

## What lives here
Capability records: methods, tools, infrastructure, techniques, prior-working solutions. Anything Arko might reach for as a **means** to achieve a focus goal or resolve a critical situation.

Examples: "phi4-14B runs at 34 tokens/s on 3080 Ti", "billo-vps has 32 GB RAM available", "photorec APFS carve recovers 84%", "Bybit paper-mode kill-switch threshold = -3% intra-day".

## Physics
Same decay as normal HOT/WARM/COLD (14-day half-life) but with a **type flag** that makes them surface preferentially when the query is action-shaped (verbs like "how do I", "which tool", "what's fastest", "can I", "what's the best way to").

| Property | Value |
|---|---|
| Tier | `ARSENAL` |
| λ | `ln(2) / 14 days` (paper 01) |
| Suppressible by FOCUS? | Yes, but boosted if arsenal item ∈ focus neighbors |
| Signature required | HMAC via `arsenal_writer.py` (signer = `loci_facts`) |
| Encrypted at rest | **No** (unlike strategies — arsenal is meant to be reachable) |
| Values check | At **write time** only (arsenal items that violate values.md are refused before storage) |

## Writing an arsenal item
```bash
python3 /Volumes/DevDrive/loci-install/scripts/arsenal_writer.py \
  --entity "gpu.3080ti" \
  --key "phi4-14b-throughput" \
  --value "34 tokens/s at fp16, 12 GB VRAM used, ollama backend" \
  --source "measured on billo-pc 2026-08-15"
```

## Retrieval
`loci_query.py` treats arsenal rows the same as HOT-tier facts for retrieval math but flags them as `tier: "ARSENAL"` in the response so downstream code (or a session) knows this is a *capability* answer, not a *fact* answer.

## Related
- [strategies.md](./strategies.md) — the password-gated tier above arsenal.
- [values.md](./values.md) — arsenal write is gated by these rules.
- [formulas.md](./formulas.md) §Tier hierarchy.
