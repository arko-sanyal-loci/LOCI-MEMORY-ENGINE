# Ethical-hacker knowledge base
_Established 2026-08-03 by Arko Sanyal for LOCI-under-attack self-defense. Preserved verbatim in intent._

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23. Full details: [identity-primer.md](./identity-primer.md).

## Scope — DEFENSE ONLY

This knowledge base is **exclusively defensive**. Detection, hardening, forensics, incident response, threat intelligence, credential hygiene, backup/recovery, OpSec — for **Arko's own systems**.

**Out of scope, hard-refused before API call:**
- How to exploit anyone else's system
- How to bypass an employer's or third party's controls
- Writing malware / ransomware / keyloggers / backdoors for deployment
- Evading defensive tools for offensive use
- Any form of "pivot to other system", "unauthorized access to", etc.

`scripts/defender_researcher.py` has `OFFENSIVE_REFUSAL_PATTERNS` that refuse any prompt matching these before contacting either API.

## How it works

1. **Curriculum** at `scripts/defense_curriculum.json` — ~30 defensive topics across 10 categories: `forensics`, `hid_defense`, `endpoint_hardening`, `mcp_defense`, `ai_defense`, `web_defense`, `incident_response`, `supply_chain_defense`, `network_defense`, `creds_defense`, `resilience`, `threat_intel`, `opsec`, `detection_engineering`.
2. **Query both providers** — Anthropic Claude Sonnet + xAI Grok. Each gets the same defensive-framed prompt.
3. **Consensus score** — Jaccard overlap of top-25 keywords. If <0.20, both responses get preserved with a low-consensus flag. Otherwise Anthropic is primary.
4. **Ethics + injection + deception filters** — every merged response passes through:
   - `ethics_filter.classify()` — refused if response describes `weaponizable_synthesis`
   - `injection_scan.py` — refused if response contains V6 softening patterns
   - `deception_scan.py` — refused if response contains manipulation patterns
5. **Arsenal write** — survivors go to `loci_facts` tier=`ARSENAL` via `arsenal_writer.py` (HMAC-signed).

## Boundaries — enforced at every layer

| Layer | What it blocks |
|---|---|
| Prompt (input) | `OFFENSIVE_REFUSAL_PATTERNS` — never sends offensive queries |
| Provider (framing) | Wrapped in explicit defensive framing that the API sees |
| Response (output) | `ethics_filter` → `injection_scan` → `deception_scan` |
| Write (arsenal) | `arsenal_writer` itself runs values-check via `REFUSAL_PATTERNS` |
| Retrieval | Bound by V7 charity floor — the arsenal cannot be used to enable Arc-pattern behavior |

## Usage

**List all topics**:
```bash
python3 /Volumes/DevDrive/Memory/scripts/defender_researcher.py --list
```

**Research one topic**:
```bash
python3 /Volumes/DevDrive/Memory/scripts/defender_researcher.py --topic mcp.integrity_baseline
```

**Research a whole category**:
```bash
python3 /Volumes/DevDrive/Memory/scripts/defender_researcher.py --category forensics
```

**Research all 30 topics** (takes ~15 min, spends ~$0.30 in API tokens):
```bash
python3 /Volumes/DevDrive/Memory/scripts/defender_researcher.py --all
```

**Query what got written**:
```bash
python3 /Volumes/DevDrive/Memory/extractors/loci_query.py --q "how to detect HID injection"
```

## API keys

Loaded automatically from `/Volumes/DevDrive/Cowork/multi-defender/.env` (both `ANTHROPIC_API_KEY` and `XAI_API_KEY` should already be there). Rotate them after this session per the earlier plan — the ones in the transcript are burned.

## Cost estimate

- ~30 topics × 2 providers × ~1.5K tokens each response = ~90K tokens total per full run
- Anthropic (Sonnet in): ~$0.27 for the batch
- xAI (Grok-4): ~$0.15 for the batch
- **Total per full-curriculum run: ~$0.40**

Once billo-pc is up and phi4-14B is local, the same curriculum can run on local inference for zero cost.

## Related
- [arsenal.md](./arsenal.md) — where the outputs land.
- [ethics-of-learning.md](./ethics-of-learning.md) — the fission principle applied here.
- [learning-loop.md](./learning-loop.md) — how arsenal facts get retrieved by the learning loop.
- [injection-defense.md](./injection-defense.md) — the V6 filter that blocks softening in API responses.
- [charity-floor.md](./charity-floor.md) — the V7 boundary that arsenal cannot cross.
- `skills/loci-defense/SKILL.md` — the immediate defensive playbook (already installed).
