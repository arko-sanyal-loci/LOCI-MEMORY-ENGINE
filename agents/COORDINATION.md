# Agent Workspace — Coordination Layer

Root layer for 32 agents (16 `ALPHA_BLUEPRINT` + 16 `BETA_RUNTIME`), one
Project/repo rather than scattered across separate code bases — matches
how Antigravity 2.0's Projects untether agents from single repos.

Antigravity 2.0's published OS-build demo ran **93** sub-agents (consistent
across every independent source checked 2026-11-18), not 240 — no source
reports that figure. 32 is a deliberate subset with headroom, not an
attempt to match the full demo scale.

## Structure
```
agents/
├── COORDINATION.md          ← you are here
├── alpha_blueprint/         ← 16 agents, research/audit/design roles
│   └── agent_NN_<role>/
│       ├── scratch/         ← per-agent working files, not committed content
│       └── ledger.jsonl     ← append-only, SHA-256-chained (same scheme as ledger/credit_ledger.jsonl)
└── beta_runtime/            ← 16 agents, runtime/infra/execution roles
    └── agent_NN_<role>/
        ├── scratch/
        └── ledger.jsonl
```

Roster taken from `mac-install`'s `loci_32_orchestrator.py` roles as-is —
not reinvented. That file's actual agent execution logic is a stub
(`asyncio.sleep(0.01)` + one DB write per agent, no real task runs) and
is not wired to these folders yet. This commit is the directory skeleton
only.

## Build roster vs. deployed runtime (resolved 2026-11-18)

**Q1 is answered.** The 32 roles are NOT 32 local models competing for
GPU VRAM. They're distributed across the real external systems doing
the actual building:

- Claude Code (this repo's agentic coding tool)
- This chat session (Claude, via claude.ai)
- Antigravity 2.0 (Google, Gemini-backed)
- Codex (OpenAI)
- ChatGPT (OpenAI API)
- xAI API (Grok)
- Nexos API — consistent with the existing multi-model consensus scanner
  already documented in `mac-install`'s defense-system (Anthropic + xAI +
  Nexos), not a new/invented term
- Claude Fable — final-pass E2E testing

This is the **build-time** roster. The two local GPUs (RTX 5060 Ti +
Intel Arc) are the **deployment target** for whatever gets built — a
separate concern from who writes the code. Still open:

1. What does the deployed/local runtime actually look like once built —
   is it meant to run the already-known local models
   (`qwen2.5:14b-instruct-q4_K_M` per `config/gpu_allocation.json` in
   this repo), the new custom runtime from the 32-agent suite zip, or
   both? This determines what "finish the LOCI engine" actually means
   as a deliverable.
2. Inference runtime for that deployed target: custom build from
   scratch, or an Ollama-API-compatible shim over a different backend?
3. Actual installed second GPU: Intel Arc **B580 (12GB)** per
   `config/gpu_allocation.json` in this repo, or **B70 (32GB)** per the
   32-agent suite zip? These are different cards — matters for what the
   deployed runtime can actually hold.
4. Speculative-decoding/"Garena" bus design — is there a reference paper,
   or is this to be researched from scratch?
