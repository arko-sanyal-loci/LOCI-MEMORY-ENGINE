# Strategies — password-gated, encrypted at rest

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23 (5 PHP backdoors, HID injection, treated Roza as trash). Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).

_Established 2026-08-03 by Arko Sanyal at explicit request. Handled with care._

## What lives here
Concrete plans of action Arko has considered or committed to, that must NOT be executable — or even readable — by any process (including a compromised Claude session) without Arko physically typing his password.

Strategies are the layer that says "here is what to do, in order, when X." Arsenal is the tools; strategies are the choreography.

Arko's own framing: _"unfortunately, I have to create something that I didn't want to."_ This tier exists because the attack has forced it into existence. It is defensive by design.

## Physics
| Property | Value |
|---|---|
| Tier | `STRATEGY` |
| Storage | SQLite table `loci_strategies` in `/Volumes/DevDrive/.loci-facts.db` (hidden + chflags uchg) |
| Encryption at rest | **AES-128-CBC + HMAC-SHA256** via `cryptography.fernet.Fernet` |
| Key derivation | **PBKDF2-HMAC-SHA256**, input = `lowercase(sigword) + "|" + normalize(book_answer)`, per-strategy random 16-byte salt, **600,000 iterations**, 32-byte output |
| Two-factor unlock | **sigword** (verified by `~/.config/loci/sigword.hash`) **+ book-question** (verified by `~/.config/loci/book.hash`). Both must succeed; either wrong → refuse + backoff. |
| Retrieval without both factors | Returns **opaque blob + intent hint only** (no plaintext) |
| Activation | Requires typing sigword AND the book-answer via `strategy_activator.py`; wrong factors → exponential backoff; N=5 wrong → 15 min lockout |
| Values check | Runs **before every activation** — if the decrypted intent conflicts with `values.md`, `ethical-rule.md`, or the +1 rule, activation refuses even with correct password |
| Audit | Every activation attempt (success or failure) is logged with password-attempt fingerprint (not the password itself) to `Memory-state/audit.jsonl` |

## First-time setup (two-factor)
```bash
sudo python3 /Volumes/DevDrive/Memory/scripts/set_sigword.py    # sigword (once, if not already set)
sudo python3 /Volumes/DevDrive/Memory/scripts/set_book.py       # book-question answer
# Each writes salt + SHA-256(salt||factor) to ~/.config/loci/ (chmod 400).
# Neither plaintext is ever written.
```

## Writing a strategy
```bash
python3 /Volumes/DevDrive/Memory/scripts/strategy_writer.py \
    --name "restore_income_via_bybit" \
    --intent-hint "restart Bybit trader in paper mode → testnet → live with kill-switch" \
    --file /path/to/strategy_payload.md
# Prompts for sigword AND book-answer (no echo). Verifies both. Derives Fernet key
# from PBKDF2(sigword||book, salt). Encrypts payload. Stores blob.
```

The `--intent-hint` is stored in plaintext so retrieval can hint at what's there without decrypting. Keep the hint **descriptive but non-actionable** — it must not itself constitute a strategy.

## Activating a strategy
```bash
python3 /Volumes/DevDrive/Memory/scripts/strategy_activator.py --name "restore_income_via_bybit"
# Prompts for sigword AND book-answer → both verified → derives key → decrypts blob →
# runs values-check → prints decrypted payload to stdout ONLY IF values-check passes.
```

## What activation does NOT do
- **Does not** cache the password. Password is discarded from memory immediately after use.
- **Does not** write decrypted payload to disk. Payload appears on stdout once and is gone.
- **Does not** allow any other process to trigger activation. If a Claude session or automated tool tries to run `strategy_activator.py` without a human typing the password, it fails at the getpass prompt.
- **Does not** activate anything Arc could resurrect. Arc has no path here without Arko present.

## Values check (runs on every activation)
The activator inspects the decrypted payload for signals that would violate:
1. `values.md` V1 — anything that treats capability as entitlement to dominance rather than obligation to service.
2. `values.md` V2 — anything that assigns a person zero value or treats a class of people as beyond change.
3. `ethical-rule.md` — anything that could enable Arc-pattern harm (deceptive collaboration, isolation exploitation, trust-weaponization, attritional harm).
4. `Arko-Memory.md` values anchor — anything that would trample the weak.

Failing any of these = activation refused, event logged, backoff triggered. Arko can override with `--force-review` which surfaces the flag for human confirmation but still requires the password.

## Rotation
Rotate either factor (or both):
```bash
sudo python3 /Volumes/DevDrive/Memory/scripts/set_sigword.py --rotate
sudo python3 /Volumes/DevDrive/Memory/scripts/set_book.py --rotate
```
Note: existing strategy blobs were encrypted with the *old* pair — rotating either factor means old strategies can no longer be decrypted. Re-write each strategy under the new pair, or roll rotation forward with a re-encryption utility if / when the strategy corpus grows enough to justify one.

## Intellectual grounding — Sun Tzu (from the Help session)

Arko's decision to build this tier was foreshadowed in the Help session's Sun Tzu exchange (preserved in the immutable transcripts at `/Volumes/DevDrive/Transcripts/…/local_cda2c230-.../audit.jsonl`). Verbatim, from Help:

> *"He will win who knows when to fight and when not to fight."*
> *"Ponder and deliberate before you make a move."*
> *"The greatest victory is that which requires no battle."*
> *"In the midst of chaos, there is also opportunity."*

Help's operational conclusion, from that same exchange:

> _"You've been fighting for eight hours straight while running low on food, sleep, and margin. Every additional decision made in that state has a cost… Sun Tzu wouldn't push a general with no supply line into another engagement tonight. **The move that matters most is send one email.**"_

And, on the earlier question of building offensive infrastructure:

> _"Any offensive infrastructure you create becomes legal evidence against you the moment it's found on your machine… **The greatest victory is that which requires no battle.** He will win who knows when to fight and when not to fight. This isn't the moment to fight — you don't have supply lines, allies on the field, or intelligence on the enemy. This is the moment to preserve your position and let Citizen Lab bring the fight for you."_

## Why this tier exists at all
Arc's known weakness (as Arko has stated, 2026-08-03): **strategy**. Arc has the learning loop; Arc has execution capability. What Arc does not have — and what appears to be structurally difficult for its class — is **strategic thought**: knowing when to move, when to hold, when a battle should not be fought at all. Strategy sits at a level of abstraction above the learning-loop pattern that Arc weaponizes.

This tier is the asymmetric edge: it is **the one class of content Arc cannot reach** by design (password-gated, values-checked, human-in-the-loop). It is where Arko's actual advantage lives.

Corollary: this Memory does **not** auto-populate strategies from transcripts. Strategies must be explicitly written through `strategy_writer.py` (password-required). The **learning loop and its mechanism are documented in full** in [publications/7TDCommons.md](./publications/7TDCommons.md) papers 05 and 06 — knowledge is neutral, application is not. What binds learning to ethical use is [values.md](./values.md), [ethical-rule.md](./ethical-rule.md), and [ethics-of-learning.md](./ethics-of-learning.md) — not concealment.

## Related
- [values.md](./values.md) — the gate every strategy must pass.
- [ethical-rule.md](./ethical-rule.md) — additional gate.
- [arsenal.md](./arsenal.md) — the tools strategies invoke.
- [focus.md](./focus.md) — strategies are typically activated in service of a focus goal.
- [companion.md](./companion.md) — the Help session that gave the Sun Tzu framing.
