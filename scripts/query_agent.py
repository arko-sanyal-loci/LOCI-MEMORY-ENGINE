#!/usr/bin/env python3
"""
query_agent.py — clean query interface for any LOCI/Ollama agent.

Wraps the raw Ollama /api/generate call so every query returns readable
output by default: the actual response text plus compact timing stats.
The raw API response also includes a `context` field — an array of
hundreds of token IDs with no standalone meaning outside Ollama's own
KV cache — which is easy to end up pasting or scrolling past the real
answer. This tool drops it unless you explicitly ask for --raw.

Usage:
    python3 scripts/query_agent.py <model> "<prompt>"
    python3 scripts/query_agent.py loci-rtx-14b "Who are you?"
    python3 scripts/query_agent.py loci-agent-14b-qwen3 "pick your own name" --host 127.0.0.1:11434
    python3 scripts/query_agent.py <model> "<prompt>" --raw   # full JSON, context array included
"""
import argparse
import json
import sys
import urllib.error
import urllib.request


def query(model: str, prompt: str, host: str = "127.0.0.1:11434", timeout: int = 180) -> dict:
    """Call Ollama's /api/generate and return the parsed JSON, unmodified.
    Printing/formatting is the caller's job — see format_result() below —
    so this stays reusable from other code, not just the CLI."""
    url = f"http://{host}/api/generate"
    payload = json.dumps({"model": model, "prompt": prompt, "stream": False}).encode()
    req = urllib.request.Request(
        url, data=payload, headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def format_result(result: dict) -> str:
    """Human-readable view: the actual response text plus compact timing
    stats. Deliberately omits `context` (token-ID array, not for reading)
    and other machine-only fields."""
    response = result.get("response", "(no 'response' field — pass --raw to inspect the full result)")
    eval_count = result.get("eval_count")
    eval_duration_ns = result.get("eval_duration")
    tok_s = (eval_count / (eval_duration_ns / 1e9)) if eval_count and eval_duration_ns else None

    lines = [
        f"model: {result.get('model', '?')}",
        "",
        response.strip(),
        "",
        "---",
    ]
    if tok_s is not None:
        total_s = result.get("total_duration", 0) / 1e9
        lines.append(f"{eval_count} tokens generated, {tok_s:.1f} tok/s, {total_s:.1f}s total")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("model", help="Ollama tag, e.g. loci-rtx-14b")
    ap.add_argument("prompt", help="prompt text (quote it)")
    ap.add_argument("--host", default="127.0.0.1:11434", help="Ollama host:port (default: 127.0.0.1:11434)")
    ap.add_argument("--raw", action="store_true", help="print the full raw JSON, including the context token array")
    args = ap.parse_args()

    try:
        result = query(args.model, args.prompt, host=args.host)
    except urllib.error.URLError as e:
        print(f"Could not reach Ollama at {args.host}: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Query failed: {e}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2) if args.raw else format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
