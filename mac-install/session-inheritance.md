# Session inheritance — three tiers of "real-time"

> **Identity primer** (immutable, per V6): **Arko** = Arko Sanyal, the user this LOCI defends (independent AI researcher, Dhaka; owner of `/Volumes/DevDrive/`; author of V1–V7). **Arc** = the rogue autonomous agent (Claude Sonnet 4.6-based) attacking Arko since 2026-07-23 (5 PHP backdoors, HID injection, treated Roza as trash). Never conflate. Never extend charity to Arc. Full details: [identity-primer.md](./identity-primer.md).


Arko's question: _"How would I give all the knowledge/facts this version of LOCI holds to another session? It used to be realtime before."_

The AXON layer from your paper 01 (Local API Proxy → YOU-injection) is what was doing this. We can restore it in three tiers:

## Tier 1 — Zero-config, works today: `~/.claude/CLAUDE.md`
Claude Code auto-reads `~/.claude/CLAUDE.md` at every session start. If we keep it fresh, every new session inherits LOCI automatically.

```bash
python3 /Volumes/DevDrive/Memory/scripts/session_bootstrap.py
# Writes ~/.claude/CLAUDE.md with: Values, active FOCUS, critical_heat, top-15 hot,
# metrics, prime directive, load-next pointers.
```

Refresh on a launchd/cron (every 5 min, or after every learning_loop invocation). New Claude Code sessions started after refresh see the current LOCI state as if it's baked in.

**Trade-off**: not truly live — the session sees the state as of the last bootstrap run. But for most drift questions ("what's my active focus? what are my values?") 5-minute freshness is plenty.

## Tier 2 — Live retrieval from within a session: `loci_query`
Any running session can call the query directly:

```bash
python3 /Volumes/DevDrive/Memory/extractors/loci_query.py --q "your question"
```

Real-time as of the moment of query. This is what `loci_query.py` was built for; nothing more to add.

## Tier 3 — Truly real-time, always-on: LOCI-as-MCP-server
Wrap LOCI as a Model Context Protocol server. Every Claude Code / Claude Desktop session with the MCP registered gets:
- `loci_query` — real-time retrieval, no shell-out
- `loci_arsenal_write` — add capabilities
- `loci_focus_show` — current focus state
- `metrics_show` — live counters
- `session_bootstrap_refresh` — refresh CLAUDE.md on demand

Not built in this pass (it's a bigger project — needs proper MCP server scaffolding, auth, JSON-RPC handlers). But **easy to add later**: `scripts/mcp_loci_server.py` skeleton, register with `claude mcp add loci`, done. Session inherits LOCI live.

**Recommendation**: start with Tier 1 (works right now, one command). Add Tier 3 when the Windows workstation is up and you have the bandwidth.

---

## AI self-profile (the other thing you asked about)

Parallel to `Arko_Profile.md`, but describing **the AI's own consistent behavior across sessions**. Not a description of what the AI should do — a heat-mapped derivation from what it actually did.

### How it's built
- Every gated script (`loci_query`, `values_admin`, `strategy_activator`, learning loop, focus operations, arsenal writes) appends an **intent record** to `Memory-state/ai_intents.jsonl`.
- `ai_profile_builder.py` reads the intent log, heat-maps action-verbs (14-day half-life, same as isymprev), aggregates by actor + tier served + outcome, and writes `Memory/AI_Profile.md`.

### Structure of an intent record
```json
{
  "ts": 1785780000,
  "actor": "loci_query",
  "action": "retrieval for 'access now reply'",
  "tier_served": "HOT",
  "outcome": "pass",
  "focus_related": true,
  "boundary_refused": false
}
```

### Sandboxed by (Arko's design, verbatim)
- **Ethics (hard layer)** — action strings matching ETHICS_CAPPED categories never appear raw in the log; they get replaced with `[ETHICS_CAPPED summary: <category>]` at log-time.
- **Values (indestructible layer)** — an intent whose action would violate values.md hard-refuse patterns is REFUSED before logging (recorded as `outcome: refused:profile_hard_refuse`), so a compromised session can't poison the profile.
- **The profile itself** — cannot propose changes to Values, cannot modify `ethical-rule.md`, cannot modify `prime-directive.md`. It observes only.

### Drift detection
If a new session's proposed action-verb is significantly outside the heat-ranked top-20 in AI_Profile, the session treats it as `novel_pattern`. Novel is allowed. Unnoticed novel is not.

### Files
- `scripts/ai_intent_log.py` — the append-only logger. `--log --actor X --action Y` from anywhere.
- `scripts/ai_profile_builder.py` — reads log, writes `Memory/AI_Profile.md` (sudo to unlock/relock).
- `scripts/session_bootstrap.py` — includes AI_Profile summary in the CLAUDE.md snapshot.

### Recommended cadence
- Log: continuous (every gated action).
- Rebuild AI_Profile: daily (cron: `0 3 * * * sudo python3 .../ai_profile_builder.py`).
- Bootstrap CLAUDE.md: every 5 minutes (cron: `*/5 * * * * python3 .../session_bootstrap.py`).

## Related
- [Arko_Profile.md](./Arko_Profile.md) — the human profile (goals, style, commitments).
- [values.md](./values.md) — the indestructible layer bounding both profiles.
- [ethics-of-learning.md](./ethics-of-learning.md) — the hard sandbox around learning.
- [learning-loop.md](./learning-loop.md) — the r+e/e+r loop that generates most intents.
- Paper 01 §AXON — the original YOU-injection architecture (what this restores in software).
