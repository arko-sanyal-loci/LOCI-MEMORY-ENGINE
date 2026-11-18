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
