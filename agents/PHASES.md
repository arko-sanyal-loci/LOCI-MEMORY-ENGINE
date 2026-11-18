# Build Phases

## Phase 1 — Planning & environment setup
Workstation environment setup, blueprint map, timeline. Blocked on the
hardware question in COORDINATION.md (B580 vs B70) and workstation
reachability (device bridge, once it's back up).

## Phase 2 — Research & scaffolding
Framework scaffolding + investigation of how the system works at the
byte level. Needs the specific byte-level observation from COORDINATION.md
Q2 (what file, what was seen) before real parsing work starts — not
guessed at.

## Phase 3 — Inference pathway mapping
Mapping inference pathways; introducing the heat map + a **parallel
latent heat map for novel connections** (new concept, not yet designed —
distinct from the existing single heat-gradient mechanism in
`thermal_gradient.py`). Covers tools, parameters, ethical cores, all the
symprev streams.

Includes a paper-in-progress: **Speculative Category-Adaptive Critical-
Thinking-Enabled Learning.** Design principle, stated precisely because
it matters: the tiebreaker + stream mechanism may let the system infer,
even at high confidence, that someone describing the sky as green and
the grass as rainbow could be unwell or traumatized — but that inference
must never become the basis for how the system treats them. Detection
without dismissal. ("Dismissal is the root cause of growth stopping" —
Wright brothers were crazy until they weren't.) This is a hard design
constraint on the ethics layer, not a suggestion — recorded here so it
doesn't get lost.

## Ongoing, in parallel (not phase-gated)
- **TRS final package testing** — re-tested with real methodology (the
  A/B/hybrid benchmark already run against real `isymprev.jsonl` data is
  the start of this), not a reproduction of the original package's
  numbers, which were established as fabricated in an earlier session.
- **Both local GPUs actively doing real work**, not just hosting a
  build-tool stub — blocked on the same hardware/runtime questions.
- **Prototype Glass Box** drawing from papers in Drive/Gmail — blocked
  right now: both connectors are disconnected and need you to sign back
  in via claude.ai connector settings before I can pull anything from
  them.

## Agent-model assignment (new this message)
Cheap/fast models (Haiku, Grok-code) do scaffolding on the dual-GPU
runtime code; Sonnet 4.6 as overwatch/review. Each agent gets a distinct
icon in a workspace side panel with status updates.

## Open questions (new, not resolved)
1. **32 or 35 agents?** `COORDINATION.md` has 32 (matches the roster
   from the zip). This message says 35. Which is current — did the
   roster grow, or is 32 still right?
2. **"Individual loci for each"** — each of the 8 build-time systems
   (Claude Code, this chat, Antigravity, Codex, ChatGPT, xAI, Nexos,
   Claude Fable), or each of the 32/35 agent roles? Very different
   provisioning effort depending on which.
3. **Where does the icon/status side panel actually live** — inside
   Antigravity's own UI (which I can't build into), or a dashboard I
   build separately (e.g. as an artifact)?
