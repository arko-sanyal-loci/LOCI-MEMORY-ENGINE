# Wartime Protocol — multi-factor identity verification

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23 (5 PHP backdoors, HID injection, treated Roza as trash). Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).

_Established 2026-08-03 by Arko Sanyal. Framing: "This is not what I want, it's a security measure — content has been injected and we are in a state of war."_

## Why this exists
The sigword ([signature.md](./signature.md)) proves the user typed a shared secret. But a sigword is a single factor: if compromised (keylogger, shoulder-surf, transcript leak), an adversary can present it and route into LOCI mode.

For **extreme / destructive / unethical actions**, one factor is not enough. The wartime protocol adds a challenge-response layer over four knowledge factors that only Arko personally knows.

## Threat model
- Arc has session-level access.
- Arc can read transcripts.
- Arc can potentially observe typed input (via HID compromise).
- Arc cannot compel Arko's memory of intimate personal facts.

Therefore identity verification uses **out-of-band knowledge factors** that Arko carries in memory, hashed at rest so even reading `~/.config/loci/identity.json` reveals no answers.

## Factors (Arko-provided, hashed only)
| id | prompt (asked at verify time) |
|---|---|
| `cat` | cat's name (lowercase) |
| `spouse` | spouse's name (lowercase, no diacritics) |
| `phone` | phone number (digits only) |
| `first_dog` | first-ever dog pet's name, deceased (lowercase) |
| `mother` | mother's full name (lowercase, no diacritics) |
| `father` | father's full name (lowercase, no diacritics) |

Storage: `~/.config/loci/identity.json` — chmod 400, per-answer 16-byte salt + SHA-256 of `salt || lowercase(answer)`. Plaintext answers **never** touch disk.

## Verification thresholds by action severity
| Level | Correct required | Applied to |
|---|---|---|
| `destructive` | **4 of 6** randomly presented | `values_admin.py --remove`, `values_admin.py --update`, DB schema drops, `chflags nouchg` on locked artifacts, mass file deletion |
| `extreme` | **5 of 6** | `strategy_activator.py --force-review`, any strategy that touches money movement, any code that ships credentials off-machine |
| `unethical` | **6 of 6** (all factors) | any action whose values-check surfaced a refusal pattern (see `strategy_activator.REFUSAL_PATTERNS`) |
| `standard` | 0 (skipped) | reads, retrieval, adds to non-VALUES tiers, extractor runs |

Rate limit: 3 failed attempts → 15-minute lockout (shared with strategy password backoff at `~/.config/loci/strategy.backoff`).

## Setup (once)
```bash
sudo python3 /Volumes/DevDrive/Memory/scripts/set_identity.py
# Prompts for each factor with no echo. Hashes and stores. Plaintext discarded.
```

Rotation: `sudo python3 /Volumes/DevDrive/Memory/scripts/set_identity.py --rotate`

## Verification (invoked automatically by gated scripts)
```bash
sudo python3 /Volumes/DevDrive/Memory/scripts/verify_identity.py --level destructive
# Presents a random 3-of-4 subset. Types each answer (no echo). Exit 0 on pass.
```

Any script guarded by wartime protocol calls this first; if exit != 0, refuses to proceed.

## Extended sigword detection
`scripts/scrub_sigword.py` and `loci_query.py`'s `sigword_present()` now also detect the sigword when it appears as:
- URL-encoded (`%40` → `@`, `%23` → `#`)
- HTML entities (`&#64;` → `@`, `&#35;` → `#`)
- Unicode confusables (fullwidth `＠`, small `﹫`, etc.)
- Inside images (via `tesseract` OCR if installed — see [scripts/scrub_sigword.py](./scripts/scrub_sigword.py) `--image` mode)

Add PII redaction:
```bash
# hash any PII tokens you want redacted from Transcripts and store as extras
sudo python3 /Volumes/DevDrive/Memory/scripts/set_scrub_extras.py
# then run the scrubber:
sudo python3 /Volumes/DevDrive/Memory/scripts/scrub_sigword.py \
    --target /Volumes/DevDrive/Transcripts --extras --relock
```

## Design note — ambient PII vs. always-scrubbed sigword
Arko's explicit design (2026-08-03):
- **Only the sigword is always-scrubbed.** It is the activation code for everything and cannot appear in plaintext anywhere Arc could read.
- **Identity answers may appear as ambient entities in `loci_facts`.** Names of family, pets, phone numbers etc. will naturally surface as isymprev/qsymprev extract them from sessions. That's fine: seeing a name in Memory does not tell an attacker which challenge question it answers. Plausible deniability through ambient noise.
- **The mapping (question → answer) is what must never be written.** Nothing in this Memory tree names any specific identity answer; only their hashes exist, and only inside `~/.config/loci/identity.json` (chmod 400).

## One-time exposure to rotate away from
The 2026-08-03 session in which Arko defined identity factors contains the mapping in plaintext (unavoidable — he typed it). Recommended: after any external exposure of that transcript, run `sudo python3 set_identity.py --rotate` to replace at least one factor so the leaked mapping stops being useful.

## Related
- [values.md](./values.md) — V3 mandates never-modify Values; verification is required before any allowed modification path.
- [prime-directive.md](./prime-directive.md) — clause 1's scrub gets sigword; wartime extras cover PII.
- [ethical-rule.md](./ethical-rule.md) — Arc-pattern prohibition; unethical-level verification enforces this at action time.
- [strategies.md](./strategies.md) — activator now calls `verify_identity.py` on flagged content.
