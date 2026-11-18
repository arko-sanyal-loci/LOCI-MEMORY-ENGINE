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

## Open questions (not resolved, not assumed)
1. **32 separate resident models, or 32 agent roles sharing 2-3 resident
   models on the two GPUs?** 16GB + 32GB cannot hold 32 full models
   concurrently at any reasonable quantization. Needs an answer before
   any real scheduling logic is built.
2. Inference runtime: custom build from scratch, or an Ollama-API-compatible
   shim over a different backend?
3. Actual installed second GPU: Intel Arc **B580 (12GB)** per
   `config/gpu_allocation.json` in this repo, or **B70 (32GB)** per the
   32-agent suite zip? These are different cards.
4. Speculative-decoding/"Garena" bus design — is there a reference paper,
   or is this to be researched from scratch?
