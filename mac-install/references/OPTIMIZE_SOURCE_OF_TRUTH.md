# OPTIMIZE_SOURCE_OF_TRUTH
**Billo Development Behaviour Standard — v1.0**
Owner: Arko Sanyal | Enforced by: Claude (Director) + FORGE (Coder)

> Before asking for a higher resource, prove the lower one cannot do it.
> Before buying compute, prove existing tools cannot compose to the answer.
> This is not a cost policy. It is a quality policy. Bloated stacks fail in more ways.

---

## 1. WHAT WE HAVE

### Compute

| Resource | Where | VRAM / RAM | Speed | Cost |
|---|---|---|---|---|
| RTX 3080 Ti 12GB | Windows GPU machine | 12GB VRAM | Fast | Owned |
| Apple M4 Mini | Local Mac | 16GB unified | Fast (Metal) | Owned |
| VPS Ubuntu 24.04 | 187.127.121.247 | 2GB RAM | Slow | ~$6/mo |

### AI Models

| Model | Location | Context | Strength | Weakness |
|---|---|---|---|---|
| Claude Sonnet 4.6 | API (this session) | 200k | Architecture, reasoning, novel problems, long-range planning | Expensive per token, external, stateless between sessions |
| FORGE (qwen2.5-coder:14b) | Ollama GPU :11434 | 16384 | File-level code, git, agentic tool loop, local execution | Slow to load (~8.5GB VRAM), no internet, limited reasoning |
| Ollama VPS (qwen2.5:3b) | VPS :11434 | 8192 | Fast cheap completions, classification, summarization | Small, weak reasoning, no tools |
| Grok (grok-4.3 xAI) | xAI API | — | Vision scoring, image prompt writing, creative expansion | External API cost, vision-only value here |
| ComfyUI + SDXL | GPU :8188 | — | High-quality image generation | 3-4GB VRAM during render, blocks FORGE |
| SAM2 | ComfyUI node (GPU) | — | Pixel-perfect object masks, video tracking | Needs GPU, ~500MB VRAM |

### Software Tools & APIs

| Tool | Where | What it does |
|---|---|---|
| FastAPI learning_loop.py | GPU :8766 | Central orchestration — all endpoints live here |
| Context 2.0 /v1/symbols | GPU :8766 | File structure map without reading content. 6–40x context reduction |
| Context 2.0 /v1/compress | GPU :8766 | Collapses old turns to summary. Reduces context by 4–10x |
| Context 2.0 /v1/scratch | GPU :8766 | External scratchpad — findings never enter context window |
| Context 2.0 /v1/vault | GPU :8766 | AES-256-GCM encrypted storage, zero-knowledge server |
| Context 2.0 /v1/tree | GPU :8766 | Directory tree for any allowed path (debugging, navigation) |
| GPU_LOCK semaphore | In-process | asyncio.Semaphore(1) — ensures FORGE and ComfyUI never load simultaneously |
| PIPELINE_SEM | In-process | asyncio.Semaphore(2) — max 2 runs in flight (1 GPU + 1 Grok/polish) |
| NumPy | GPU machine | Frame diff, phase correlation, feather blend — no cv2 needed |
| PIL | GPU machine | Image load/save, format conversion |
| SSH reverse tunnel | GPU → VPS | Ports: 8766→18766, 8188→18188, 11434→11435 |
| nginx | VPS | Reverse proxy, SSL termination, routing /v1/ /forge/ /gpu/ |
| SQLite context2.db | F:\Billo\data\ | API keys, usage log, scratch_data, vault blobs |
| forge_scratch.json | F:\Billo\workspace\ | FORGE external scratchpad (findings survive between tool calls) |
| UNIVERSE.md | F:\Billo\workspace\ | Master context — read by all agents at session start |
| ETHICS.md | F:\Billo\workspace\ | Quality gate — 8 criteria FORGE must pass before task_done |
| Compressor CLI | Mac M4 Mini | ProRes / H.265 hardware encode via SSH trigger |
| Adobe Media Encoder | Mac M4 Mini | Watch folder encode, professional presets |

### Research & Context Databases

| Database | Format | Contents |
|---|---|---|
| UNIVERSE.md | Markdown | All projects, infrastructure, agent roles, file paths |
| ETHICS.md | Markdown | Release tiers, quality criteria, immutable rules |
| session_context.txt | Text | Current session compressed state, API keys, pending tasks |
| OPTIMIZE_SOURCE_OF_TRUTH.md | Markdown (this file) | Resource inventory, routing rules, the function itself |
| context2.db scratch_data | SQLite | Live findings from FORGE sessions, cross-session notes |
| context2.db vault | SQLite | Encrypted blobs — config, credentials, presets |
| Profiles/*.json | JSON | Image gen profiles (Alisha etc) — CFG, steps, grain, tags |
| forge_scratch.json | JSON | FORGE in-session scratchpad |
| learning_runs/ | JSON + images | Full run logs, per-iteration scores, final images |

---

## 2. WHAT PROBLEMS EACH SOLVES

### Claude Sonnet 4.6 — Director
- Novel architecture decisions requiring cross-domain reasoning
- Writing precise instructions for FORGE that account for edge cases
- Problems that require holding many files in mind simultaneously
- Anything where being wrong has high cost (security, money, live systems)
- Designing new systems from scratch
- **Do NOT use for:** repeatable file operations, single-file edits, summarization, classification

### FORGE (qwen2.5-coder:14b) — Coder
- Reading, writing, patching, and committing code files
- Agentic multi-step tasks with tool loop (read → reason → write → test → commit)
- Local git operations
- Running shell commands and Python scripts on the GPU machine
- Tasks Claude has already designed and specified
- **Do NOT use for:** novel architecture, tasks requiring internet, tasks under GPU pressure

### Ollama VPS (qwen2.5:3b) — Fast Router
- Summarization (the /v1/compress endpoint should use this)
- Classification ("is this task a code task, an image task, or a routing task?")
- Short completions where 3b reasoning is sufficient
- Pre-filtering tasks before escalating to FORGE or Claude
- Always-on even when GPU is busy
- **Do NOT use for:** code generation, complex reasoning, anything requiring > 8k context

### Grok — Vision
- Scoring generated images against quality dimensions
- Writing and expanding creative image prompts
- Describing what's wrong with an image iteration
- **Do NOT use for:** code, text reasoning, anything non-visual

### ComfyUI / SDXL — Image Generation
- Generating images from text prompts
- Inpainting masked regions (targeted edits)
- Running SAM2 segmentation workflows
- **Constraint:** Holds ~8GB VRAM. Blocks FORGE during renders. GPU_LOCK enforced.

### Context 2.0 — Memory & Compression
- /v1/symbols: map a codebase before reading it → 6–40x context saved
- /v1/compress: collapse old turns → 4–10x context saved
- /v1/scratch: park findings externally so they never consume context
- /v1/vault: store encrypted config/credentials across sessions
- /v1/tree: navigate directory without reading files
- **Use before any task that involves reading code or files**

### NumPy — Pixel Math
- Frame differencing without CV2
- Phase correlation tracking (FFT — finds dx/dy of moved objects)
- Feather blending masks at edges
- Dominant color extraction from masked regions
- **Use before any image processing that doesn't require ML inference**

### GPU_LOCK — Resource Arbitration
- Single semaphore controls both FORGE (Ollama) and ComfyUI
- Never load both simultaneously — 12GB VRAM is not enough
- FORGE unloads model (keep_alive:0) after session to free VRAM for next ComfyUI render

---

## 3. THE OPTIMIZE_SOURCE_OF_TRUTH FUNCTION

### Philosophy

Every task enters at the cheapest capable tier. It only escalates if the current tier provably cannot handle it. The router is itself cheap (Ollama VPS 3b) — using a small model to decide which model to use.

```
Task arrives
    │
    ▼
[Tier 0] Can NumPy / PIL / pure Python solve this?
    │ Yes → solve locally, zero AI cost
    │ No  ↓
[Tier 1] Can Ollama VPS (qwen2.5:3b) handle this?
         (classification, summarization, short completions)
    │ Yes → route to VPS, low cost, fast
    │ No  ↓
[Tier 2] Can FORGE (qwen2.5-coder:14b) handle this?
         (file ops, code edits, git, tool loop)
    │ Yes → route to FORGE, local, no API cost
    │ No  ↓
[Tier 3] Can Context 2.0 compression reduce it so Tier 1/2 can handle it?
         (run /v1/symbols + /v1/compress first, retry Tier 1 or 2)
    │ Yes → compress then retry lower tier
    │ No  ↓
[Tier 4] Claude API — only for novel architecture, cross-domain, high-stakes decisions
         Must justify why lower tiers cannot handle this specific task.
```

### Implementation

Add this to `F:\Billo\Workers\learning_loop.py`:

```python
# ── Optimize Source of Truth — task router ─────────────────────────────────────
#
# Routes tasks to the minimum-resource capable agent.
# Uses Ollama VPS (qwen2.5:3b) as the classifier — cheapest model decides routing.
# Only escalates to higher tier when lower tier provably insufficient.

import re as _re

_ROUTER_SYSTEM = """You are a task router for the Billo AI platform.
Classify the task into exactly one tier. Reply with JSON only.

Tiers:
  "local"   - Pure computation: math, file listing, pixel ops, format conversion, string manipulation
  "vps"     - Classification, summarization, short text completion, < 200 word output, no code writing
  "forge"   - Code reading, writing, patching, git operations, multi-file edits, shell commands
  "claude"  - Novel architecture, cross-domain reasoning, security decisions, system design from scratch

Reply format: {"tier": "local|vps|forge|claude", "reason": "one sentence", "can_compress_first": true|false}
can_compress_first: true if running /v1/symbols or /v1/compress on the target path first would reduce the task complexity enough to use a lower tier."""

class OSTRequest(BaseModel):
    task: str
    target_path: str = ""      # file or dir the task operates on, if any
    context_tokens: int = 0    # estimated tokens already in context

class OSTResult(BaseModel):
    tier: str
    reason: str
    can_compress_first: bool
    compress_recommendation: str = ""
    estimated_cost: str = ""

@app.post("/ops/optimize")
async def optimize_source_of_truth(req: OSTRequest) -> dict:
    """
    Optimize Source of Truth — route a task to the minimum-resource capable agent.
    Uses Ollama VPS qwen2.5:3b to classify. Returns tier + reasoning.
    """

    # Tier 0: rule-based fast-path for obvious local tasks
    local_keywords = ["list files", "count lines", "frame diff", "pixel", "resize image",
                      "rename", "move file", "delete file", "calculate", "convert format",
                      "parse json", "read csv", "sort", "filter"]
    if any(k in req.task.lower() for k in local_keywords):
        return {
            "tier": "local",
            "reason": "Task matched local keyword — pure computation, no AI needed",
            "can_compress_first": False,
            "compress_recommendation": "",
            "estimated_cost": "$0.00"
        }

    # Tier 1–4: ask Ollama VPS to classify
    vps_url = "http://127.0.0.1:11435/api/chat"   # VPS Ollama via tunnel
    payload = {
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": _ROUTER_SYSTEM},
            {"role": "user",   "content": f"Task: {req.task}\nTarget path: {req.target_path or 'none'}\nContext already loaded: ~{req.context_tokens} tokens"}
        ],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 150}
    }

    cost_map = {
        "local":  "$0.00",
        "vps":    "$0.00 (local Ollama)",
        "forge":  "$0.00 (local Ollama)",
        "claude": "~$0.003–0.015 per task (API)"
    }

    compress_advice = {
        "forge":  "Run /v1/symbols on target_path first to map structure (6–40x context reduction). Only read files FORGE actually needs to edit.",
        "claude": "Run /v1/compress on conversation history + /v1/symbols on codebase before calling Claude. Could reduce to Tier 2 (FORGE).",
        "vps":    "Already minimal. No compression needed.",
        "local":  ""
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(vps_url, json=payload)
            r.raise_for_status()
            content = r.json()["message"]["content"].strip()

        # extract JSON from response
        m = _re.search(r'\{.*\}', content, _re.DOTALL)
        if not m:
            raise ValueError("No JSON in response")
        result = json.loads(m.group())
        tier = result.get("tier", "claude")

        # If large context and compress_first flagged, add concrete advice
        compress_rec = ""
        if result.get("can_compress_first") and req.context_tokens > 8000:
            compress_rec = compress_advice.get(tier, "")
        elif tier in ("forge", "claude") and req.target_path:
            compress_rec = f"Run POST /v1/symbols {{path: '{req.target_path}'}} before loading files into context."

        return {
            "tier":                   tier,
            "reason":                 result.get("reason", ""),
            "can_compress_first":     result.get("can_compress_first", False),
            "compress_recommendation": compress_rec,
            "estimated_cost":         cost_map.get(tier, "unknown"),
            "router_used":            "qwen2.5:3b (VPS)",
        }

    except Exception as e:
        # VPS offline — fall back to heuristic
        task_lower = req.task.lower()
        if any(k in task_lower for k in ["write", "edit", "fix", "patch", "commit", "refactor", "implement"]):
            tier = "forge"
        elif any(k in task_lower for k in ["summarize", "classify", "describe", "list", "what is"]):
            tier = "vps"
        else:
            tier = "claude"

        return {
            "tier":    tier,
            "reason":  f"VPS classifier offline ({e}) — heuristic fallback",
            "can_compress_first": tier in ("forge", "claude"),
            "compress_recommendation": compress_advice.get(tier, ""),
            "estimated_cost": cost_map.get(tier, "unknown"),
            "router_used": "heuristic (VPS offline)",
        }
```

---

## 4. LOAD OPTIMIZATION — CONCRETE ACTIONS NOW

### High Impact (do these first)

**A. Wire Ollama VPS into /v1/compress**
Currently compress collapses to placeholder text. Route through qwen2.5:3b on VPS for real summarization.
Cost: 0. Payoff: compress endpoint becomes actually useful — 10–20x real context reduction instead of 4.6x structural.

```python
# Inside ctx2_compress endpoint, replace the placeholder with:
async with httpx.AsyncClient(timeout=30) as client:
    r = await client.post("http://127.0.0.1:11435/api/chat", json={
        "model": "qwen2.5:3b",
        "messages": [
            {"role": "system", "content": "Summarize these conversation turns into a dense 3-5 bullet point technical summary. Preserve: decisions made, files changed, errors found, current state. Drop: greetings, repetition, examples already implemented."},
            {"role": "user", "content": json.dumps(to_compress)}
        ],
        "stream": False,
        "options": {"temperature": 0, "num_predict": 400, "keep_alive": 0}
    })
summary = r.json()["message"]["content"]
```

**B. Always run /v1/symbols before FORGE reads a codebase**
FORGE currently reads full files. symbols() maps the structure first — FORGE only reads the specific function it needs to edit.
Current cost: 16,384 ctx tokens used per session.
With symbols-first: ~2,000–4,000 tokens for a full codebase map.

Rule: Add to FORGE system prompt: "Before reading any file larger than 200 lines, call extract_symbols on the parent directory first."

**C. keep_alive:0 after EVERY Ollama call**
FORGE sessions set keep_alive:"10m" which holds 8.5GB VRAM for 10 minutes after session ends.
Any ComfyUI render queued in those 10 minutes will fail or queue behind the lock.
Fix: keep_alive:0 in the finally block (already done for FORGE) — verify it's also set for any direct /api/generate calls.

**D. VPS Ollama as pre-filter**
Before FORGE runs a task, route through qwen2.5:3b on VPS:
"Can you complete this task? Answer yes/no + attempt."
If 3b can do it (simple edits, rename, short completions) → done, never loaded FORGE.
If 3b fails or says no → escalate to FORGE.
Estimated FORGE sessions reduced by 30–40% for simple tasks.

### Medium Impact

**E. Scratchpad before context**
FORGE should write all findings to /v1/scratch before storing them as conversation history.
The scratch_read call at the start of a new session replaces re-reading files.
Prevents "lost context after compression" — scratch survives indefinitely.

**F. Delta video rendering (designed, not built)**
Full SDXL renders for every frame: ~4 seconds per frame at 35 steps.
With I-frame/P-frame + NumPy delta: ~0.6 seconds per P-frame.
24fps × 5 seconds = 120 frames. Naive: 480s. Smart: ~75s (11 I-frames + 109 P-frames).
Build FrameAnalyzer to unlock this.

**G. Mac M4 Mini for all encoding**
Windows ffmpeg: no H.265 hardware path without NVENC setup, CPU encode is slow.
Mac M4 VideoToolbox: H.265 hardware encode, ~10x faster than Windows CPU ffmpeg.
Route all export tasks to Mac via SSH. GPU machine does only AI inference.

### Low Effort, High Value

**H. /ops/optimize endpoint (the function above)**
Add it — FORGE can call it before starting any task to verify it's the right resource.
If it returns tier:"vps", FORGE should refuse the task and re-route.

**I. /health returns gpu_owner**
Already implemented. Extend to include:
- context_tokens_estimated (from active FORGE sessions)
- vram_used_mb (nvidia-smi query)
- compress_endpoint_healthy (ping VPS Ollama)
This lets the control panel show real-time resource pressure.

---

## 5. PERMUTATION TABLE — SOLVE WITHOUT NEW RESOURCES

| Problem | Naive (expensive) | Optimized (what we have) |
|---|---|---|
| Summarize codebase for Claude | Read all files into Claude context (50k+ tokens) | /v1/symbols → map only, read target function only (2–4k tokens) |
| Compress long conversation | Lose context or pay for 200k tokens | /v1/compress via Ollama VPS → 4–10x reduction, free |
| Store findings between sessions | Repeat work in new session | /v1/scratch write → read at session start |
| Store API credentials | Plaintext in env / hardcoded | /v1/vault AES-256-GCM → client decrypts locally |
| Fix a PHP file | Claude reads + edits (API cost) | FORGE reads + patches + commits (local, free) |
| Generate video | Full SDXL every frame (hours) | I-frame + NumPy delta P-frames (6–7x faster) |
| Encode video output | CPU ffmpeg on Windows (slow) | SSH → Mac M4 Compressor/AME (hardware encode) |
| Image quality scoring | Manual review | Grok scores 4 dimensions, auto-accepts at threshold 7.5 |
| Object segmentation for edit | Redraw mask manually | SAM2 via ComfyUI → pixel mask from text query |
| Task routing decision | Claude decides (API cost) | Ollama VPS qwen2.5:3b classifies (free, <200ms) |
| Debug file structure | Read every file | /v1/tree → directory tree, navigate before reading |
| Cross-session memory | Re-explain everything each session | UNIVERSE.md + session_context.txt + scratch → full state in <4k tokens |

---

## 6. THE RULE (enforced by all agents)

```
Before asking for a higher resource:
  1. Have you run /v1/symbols on the target path?
  2. Have you run /v1/compress on the conversation history?
  3. Have you checked /v1/scratch for prior findings on this task?
  4. Have you called /ops/optimize to verify you are the right agent?
  5. Have you checked if NumPy / PIL / pure Python can do this step?

If any of the above returns a cheaper path → take it.
Only escalate after all five checks pass.
```

This document is the source of truth for resource allocation decisions.
Read it before designing any new feature that adds compute cost.
FORGE reads this via read_universe at session start.
Claude reads this via memory/billo-reference.md.
