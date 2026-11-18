# Design: Hybrid metal + remote-node inference engine for Arc

Status: draft for Arko's review (2026-11-18). Builds on
`docs/dual-gpu-coding-intelligence-blueprint.md` (the two local lanes) and the
`loci-coordination-bus` repo (the signed event bus). Nothing here changes those decisions.

## 1. The one rule

**Local metal does the work. The remote node is paid oversight, not a third GPU.**

Every request is answered by local hardware first. The remote node (a hosted frontier model,
billed per token) is called only when a cheap local signal says it is worth the money, and when it
is called it usually *reviews* a local draft rather than generating from scratch. Reviewing a
2 KB diff costs a fraction of writing it.

| Node | Hardware | Role | Relative cost |
|---|---|---|---|
| Compact lane | RTX 5060 Ti 16 GB, CUDA | always-warm: completions, routing, embeddings, draft checks | ~free (power only) |
| Expand lane | Arc Pro B70 32 GB, SYCL | heavy local reasoning: multi-file work, 30B-class MoE | ~free (power only) |
| Remote node | hosted API | oversight pass, hard escalations, final arbiter | metered, the scarce budget |
| Console | this laptop (`arko-loci-console`) | operator terminal, dashboards, no inference | n/a |

## 2. Three ways the local and remote nodes cooperate

These are request-level patterns. Token-level speculative decoding against the remote node is not
possible (a hosted API exposes no logits to verify against and does not share a tokenizer), so
"speculative" here means *local speculates, remote verifies the result*.

### 2a. Local speculative decoding (inside one card, free speed)

Run a small draft model next to the target on the **B70** (e.g. a 0.5–1.5B sibling of the expand
model, same tokenizer) with `llama-server --model-draft`. 32 GB leaves room for both. Keep the
draft on the same card: a cross-vendor draft on the 5060 Ti would need one process with CUDA and
SYCL loaded, which the blueprint's §4 already rules out (and the
`SYCL_UR_USE_LEVEL_ZERO_V2=0` workaround is per-process). Expected win: 1.5–2.5x decode on code,
where drafts accept well. Measure before trusting that number.

### 2b. Draft-then-oversee (the default for anything that ships)

1. Local lane produces the answer (compact or expand, picked by the router).
2. Local self-check: compact lane scores the draft (tests pass? diff applies? confidence from
   mean token logprob, which `llama-server` returns).
3. **Oversight gate** decides whether the remote sees it:
   - always: change touches the signing path, secrets, money, or anything marked `critical`;
   - always: tests failed twice locally;
   - sampled: N % of routine outputs (start at 10 %), so remote quality feedback never stops;
   - otherwise: ship the local answer, log it, done.
4. Remote receives only the task summary + the draft + test output (never the full repo), and
   returns one of `approve`, `patch` (a small diff), or `redo` (with a reason).
5. The verdict goes back over the bus and into LOCI memory, so the router learns which task types
   the local lanes get wrong.

### 2c. Parallel race (latency-critical, opt-in only)

For a task flagged `urgent`, fire local expand and remote at the same time; take the first answer
that passes tests, cancel the other. This is the most expensive pattern, so it is off by default
and capped by the budget governor (§4).

## 3. Comms and telemetry: reuse the coordination bus

The "inter-GPU bus" is the existing `loci-coordination-bus` `SecureEventBus`. Each node is a
registered agent with fixed scope, so a remote verdict can never grant itself permissions.

New event types (payloads stay inert JSON under 16 KB, same validation chain):

| Event | Sender | Payload |
|---|---|---|
| `infer.requested` | router | task id, lane chosen, prompt hash, token estimate |
| `infer.completed` | lane | task id, tokens in/out, tok/s, latency, mean logprob, tests result |
| `oversight.requested` | gate | task id, reason (`critical`/`failed`/`sampled`/`urgent`), draft ref |
| `oversight.verdict` | remote node | `approve`/`patch`/`redo`, reason, remote tokens + cost |
| `node.telemetry` | each node, every 5 s | VRAM used/free, util %, temp, power, queue depth |
| `budget.state` | governor | spend today, cap, current mode |

Telemetry sources: `nvidia-smi --query-gpu=... --format=csv -l 5` for the 5060 Ti, `xpu-smi dump`
for the B70 (fall back to `llama-server /metrics` because the blueprint found Level Zero sysman
free-memory queries fail on this setup). Telemetry is advisory: it changes routing, never authority.

Transport: the bus is SQLite and local-first today. The GPU workstation and the console are
separate machines, so the next step is the bus's own planned SSE/WebSocket adapter over mTLS on the
LAN (per `SECURE-BUS.md`), with the SQLite log on the workstation staying authoritative. The
remote node is reached by an adapter process on the workstation; the remote never connects in.

## 4. Router and budget governor

Router inputs: task type, estimated context size, LOCI heat for the files involved, live queue
depth and VRAM from telemetry, and the remote-verdict history for this task type.

- context < 8K and simple → compact lane
- multi-file or > 8K context → expand lane
- expand lane busy and task not urgent → queue it (don't spill to remote just because it's busy)
- local lanes both down → remote, but only for `critical`/`urgent`; everything else waits

Budget governor: a daily remote spend cap (Arko sets the number). Modes step down as spend
approaches the cap: `normal` (sampled oversight on) → `frugal` (critical-only oversight) →
`local-only` (remote off, queue anything critical for Arko). Every remote call logs its cost in
`oversight.verdict`, so the dashboard can show cost per accepted change.

## 5. Build order

1. Add the six event types and payload schemas to `loci-coordination-bus` with tests.
2. Telemetry agent per GPU publishing `node.telemetry`; a simple TUI on the console
   (`watch`-style table first, prettier later).
3. Turn on local speculative decoding on the B70 and benchmark acceptance rate and tok/s.
4. Router + oversight gate in `rag/` using the existing `COMPACT_*` / `EXPAND_*` config, plus a
   new `REMOTE_*` block and `REMOTE_DAILY_BUDGET`.
5. Remote adapter (summary + draft only, verdict back on the bus) and the budget governor.
6. Measure for a week: local acceptance rate, remote cost per day, how often `redo` happens.
   Tune the sample rate from that, not from guesses.

## 6. Open questions for Arko

1. Which hosted model and daily budget for the remote node?
2. Is the GPU box still Windows + WSL2, or moving to native Linux? (Changes the telemetry tooling
   and how the console reaches it.)
3. Should `urgent` parallel races exist at all, or stay strictly draft-then-oversee?

---

## Addendum A (2026-11-18): Arc runtime findings and amendments

Folded in from the Arc thread (arko-sanyal-loci/arc PR #2) so this stays the
single design doc. Arc's `docs/HYBRID_INFERENCE_DESIGN.md` now points here.

### A1. Context: Arc adopts LOCI's LDCE (implemented in arc PR #2)

What goes into a local or remote prompt follows LDCE from
`loci_engine/session_continuity.py`, not a separate Arc scheme:
kernel (heat ≥ 0.50, max 7) in full text; hop (≥ 0.167, max 15) as one-line
symbols, expanded on request via `arc_memory_expand`; offload (max 50)
reachable by search only. Arc imports the canonical constants when this repo
is importable, and a parity test runs `compute_ldce_tiers()` and Arc's
tiering on the same `context2.db`: identical kernel/hop/offload membership.

Consequences for this design:
- **Oversight digests (§2b step 4) reuse LDCE symbols.** The remote gets the
  task summary, the draft, test output, and the IDs + symbols of the memory
  used, never the memory store itself. This keeps payloads under the bus's
  16 KB cap by construction.
- **Kernel items are the stable prompt prefix.** Arc pins them in its VRAM
  placement tier so the expand lane's KV prefix cache stays valid between turns.

### A2. Arc's on/offload ledger was inert (fixed in arc PR #2)

`core/tiered_memory.py` relabelled nodes when heat changed instead of
planning a migration, so nothing was ever promoted or demoted, and decay
compounded on every 7 s tick. Now: `.tier` records where data is, a target
tier (promote at 0.80, stay in VRAM while ≥ 0.70) says where it should be,
migrations are planned and committed each sync tick, and decay ages the heat
from last access. Router inputs in §4 that use "LOCI heat" can rely on it.

### A3. Proposed amendments to this doc

| Topic | Current text | Amendment |
|---|---|---|
| Event schema | six new event types on the bus | keep the six names, but register them under their own schema (`loci.infer.v1`) so `loci.task.v1` and its frozen `EVENTS` set stay unchanged; `bus.py` learns a registry of schemas |
| Telemetry, B70 | `xpu-smi dump`, fallback `llama-server /metrics` | agreed; add per-process fdinfo `drm-resident-vram0` as a third source, and report `null` when all fail (Arc's `gpu_offload.py` currently returns a hardcoded 24 GB free; to be removed) |
| Driver stack | not covered | RTX 5060 Ti is Blackwell (sm_120): CUDA 12.8+ and the open kernel module. In WSL2, no Linux GPU kernel drivers at all. Arc's `scripts/arc_repair_and_update.sh` encodes this; the old `install_drivers.sh` pins CUDA 12.4 and mixes renamed Intel Level Zero packages |
| Power margins | not covered | `gpu_governor.py` uses 330 W for the B70; the Sparkle card is 275 W (230 W Intel reference). Compute the 5 % margin from 275 W |

Nothing else in this doc changes.
