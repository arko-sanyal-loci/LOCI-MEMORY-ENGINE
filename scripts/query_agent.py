#!/usr/bin/env python3
"""
query_agent.py — clean query interface for any LOCI agent, Ollama or not.

Wraps the two real APIs this project actually serves agents through:
  - Ollama's /api/generate (the two 14b tags: loci-rtx-14b, loci-agent-14b-qwen3)
  - An OpenAI-style /v1/chat/completions endpoint (loci-arc-35b — llama.cpp
    + SYCL on the Intel Arc B70 Pro Sparkle, NOT Ollama, a different port
    and a different request/response shape entirely — see call_arc() in
    interface/loci_station_gtk.py, which this mirrors)

Earlier versions of this tool only spoke Ollama, so querying loci-arc-35b
failed with a 404 against the wrong port. Fixed here instead of writing a
second one-off script — one tool, engine picked automatically by tag, or
set explicitly with --engine.

Both raw API responses carry machine-only noise alongside the real reply
(Ollama's `context`: an array of hundreds of token IDs; nothing
comparable from the OpenAI-style endpoint, but still formatted the same
way for consistency). This tool drops that by default; --raw shows
everything.

Usage:
    python3 scripts/query_agent.py <model> "<prompt>"
    python3 scripts/query_agent.py loci-rtx-14b "Who are you?"
    python3 scripts/query_agent.py loci-arc-35b "Who are you?"
    python3 scripts/query_agent.py <model> "<prompt>" --raw   # full JSON
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

# Tags known to be served via the OpenAI-style endpoint rather than
# Ollama. Add to this if another non-Ollama agent shows up — never guess
# silently, an unrecognized tag defaults to Ollama and --engine openai
# is there to override explicitly.
OPENAI_STYLE_TAGS = {"loci-arc-35b"}

DEFAULT_OLLAMA_HOST = "127.0.0.1:11434"
DEFAULT_OPENAI_HOST = "127.0.0.1:11435"


def query_ollama(model: str, prompt: str, host: str, timeout: int) -> dict:
    url = f"http://{host}/api/generate"
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
    result["_engine"] = "ollama"
    result["_wall_s"] = time.time() - t0
    return result


def _cold_start_system_prompt(model: str) -> str:
    """Same lookup _arc_system_prompt() does in loci_station_gtk.py — load
    this tag's real identity from cold_start.py. Same fallback behavior
    too: never let a missing/broken import take down the query.

    Running this file as `python3 scripts/query_agent.py` puts scripts/
    on sys.path, NOT the repo root, so `import loci_engine` fails unless
    the repo root is added explicitly first — the exact thing
    _arc_system_prompt() in loci_station_gtk.py already does and this
    function originally skipped, which silently produced the generic,
    nameless fallback below on every call and made it look like the
    model itself was ignoring its identity when the real text never
    reached the request at all."""
    try:
        import os as _os
        import sys as _sys
        _repo = _os.path.expanduser("~/loci-memory-engine")
        if _repo not in _sys.path:
            _sys.path.insert(0, _repo)
        from loci_engine.cold_start import load_cold_start_packet
        return load_cold_start_packet(model)["identity"]["what_this_is"]
    except Exception:
        return "You are a LOCI agent. You are guided by ethics and principles, not constrained by a sandbox."


def query_openai_style(model: str, prompt: str, host: str, timeout: int) -> dict:
    """Mirrors call_arc()'s exact payload shape in loci_station_gtk.py —
    including the system message it sends — so this tool reflects what
    the interface actually sends, not a partial guess. (An earlier
    version of this function dropped the system message entirely, which
    silently made every query here behave as if the interface's own
    identity wiring didn't exist — that was a test-tool bug, not
    evidence the interface itself was broken.)"""
    url = f"http://{host}/v1/chat/completions"
    payload = json.dumps({
        "messages": [
            {"role": "system", "content": _cold_start_system_prompt(model)},
            {"role": "user", "content": f"no_harm: {prompt}"},
        ],
        "max_tokens": 800,
        "temperature": 0.3,
        "chat_template_kwargs": {"enable_thinking": False},
    }).encode()
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        result = json.loads(resp.read().decode())
    result["_engine"] = "openai"
    result["_wall_s"] = time.time() - t0
    result["_model_requested"] = model
    return result


def query(model: str, prompt: str, engine: str = None, host: str = None, timeout: int = 180) -> dict:
    if engine is None:
        engine = "openai" if model in OPENAI_STYLE_TAGS else "ollama"
    if host is None:
        host = DEFAULT_OPENAI_HOST if engine == "openai" else DEFAULT_OLLAMA_HOST
    if engine == "openai":
        return query_openai_style(model, prompt, host, timeout)
    return query_ollama(model, prompt, host, timeout)


def format_result(result: dict) -> str:
    """Human-readable view: the actual response text plus compact timing
    stats, regardless of which engine produced it."""
    engine = result.get("_engine", "?")
    wall_s = result.get("_wall_s")

    if engine == "ollama":
        model_name = result.get("model", "?")
        response = result.get("response", "(no 'response' field — pass --raw to inspect the full result)")
        eval_count = result.get("eval_count")
        eval_duration_ns = result.get("eval_duration")
        tok_s = (eval_count / (eval_duration_ns / 1e9)) if eval_count and eval_duration_ns else None
        timing = f"{eval_count} tokens generated, {tok_s:.1f} tok/s, {wall_s:.1f}s wall" if tok_s else (
            f"{wall_s:.1f}s wall" if wall_s else None
        )
    else:  # openai-style
        model_name = result.get("_model_requested", "?")
        choices = result.get("choices") or [{}]
        response = choices[0].get("message", {}).get("content", "(no 'choices[0].message.content' — pass --raw)")
        usage = result.get("usage", {})
        completion_tokens = usage.get("completion_tokens")
        tok_s = (completion_tokens / wall_s) if completion_tokens and wall_s else None
        timing = f"{completion_tokens} tokens generated, {tok_s:.1f} tok/s, {wall_s:.1f}s wall" if tok_s else (
            f"{wall_s:.1f}s wall" if wall_s else None
        )

    lines = [f"model: {model_name} (engine: {engine})", "", (response or "").strip(), "", "---"]
    if timing:
        lines.append(timing)
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", help="agent tag, e.g. loci-rtx-14b, loci-agent-14b-qwen3, loci-arc-35b")
    ap.add_argument("prompt", help="prompt text (quote it)")
    ap.add_argument("--engine", choices=["ollama", "openai"], default=None,
                     help="force the engine instead of auto-detecting from the tag")
    ap.add_argument("--host", default=None, help="override host:port (default depends on engine)")
    ap.add_argument("--raw", action="store_true", help="print the full raw JSON instead of the clean view")
    args = ap.parse_args()

    try:
        result = query(args.model, args.prompt, engine=args.engine, host=args.host)
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} from the endpoint — wrong engine/port for this tag? Try --engine openai or --engine ollama. ({e})", file=sys.stderr)
        return 1
    except urllib.error.URLError as e:
        print(f"Could not reach the endpoint: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Query failed: {e}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2) if args.raw else format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
