#!/usr/bin/env python3
"""
tools/context2_client.py - CLI Management Tool for LOCI & Billo

Usage:
    python tools/context2_client.py handover <session_id>
    python tools/context2_client.py query "search phrase"
    python tools/context2_client.py compress <file_or_text>
    python tools/context2_client.py health
"""

import sys
import os
import json
import argparse
import urllib.request
import urllib.error

API_BASE = os.getenv("BILLO_API_BASE", "http://127.0.0.1:8000")


def api_get(endpoint: str):
    url = f"{API_BASE}{endpoint}"
    req = urllib.request.Request(url, headers={"User-Agent": "Context2Client/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"Error connecting to API at {url}: {e}", file=sys.stderr)
        sys.exit(1)


def api_post(endpoint: str, data: dict):
    url = f"{API_BASE}{endpoint}"
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json", "User-Agent": "Context2Client/1.0"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as e:
        print(f"Error connecting to API at {url}: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_handover(session_id: str):
    res = api_get(f"/v1/context/handover/{session_id}")
    print("\n--- LOCI SESSION HANDOVER ---")
    print(f"Session ID:       {res.get('session_id')}")
    print(f"Estimated Tokens: {res.get('estimated_tokens')} (~61% token reduction)")
    print("-----------------------------\n")
    print(res.get("payload", ""))
    print("\n-----------------------------")


def cmd_query(query_str: str):
    res = api_post("/v1/context/query", {"query": query_str, "limit": 10})
    print(f"\n--- LOCI CONTEXT QUERY: '{query_str}' ---")
    eff = res.get("efficiency", {})
    print(f"Query Hash:       {res.get('query_hash')}")
    print(f"CER Ratio:        {eff.get('ratio')}x ({eff.get('grade')}) {eff.get('emoji', '')}")
    print(f"Token Scale:      {eff.get('scale_bar')}")
    print(f"Monetary Savings: {eff.get('monetary', {}).get('display', 'N/A')}")
    print("\n--- ENTITY HITS ---")
    for hit in res.get("hits", []):
        sym = " [LINK]" if hit.get("is_symlink") else ""
        print(f"• {hit.get('display_name')} ({hit.get('entity_type')}) [Hits: {hit.get('hit_count')}]{sym}")


def cmd_compress(target: str):
    if os.path.exists(target):
        with open(target, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    else:
        text = target

    res = api_post("/v1/compress", {"session_id": "cli_session", "text": text})
    print("\n--- VPS CONTEXT COMPRESSION ---")
    print(f"Original Tokens:   {res.get('original_tokens')}")
    print(f"Compressed Tokens: {res.get('compressed_tokens')}")
    print(f"Tokens Saved:      {res.get('tokens_saved')}")
    print(f"Method:            {res.get('method')}")
    print("-------------------------------\n")
    print(res.get("compressed_text", ""))


def cmd_health():
    res = api_get("/api/health")
    print("\n--- BILLO / LOCI SYSTEM HEALTH ---")
    print(json.dumps(res, indent=2))


def main():
    parser = argparse.ArgumentParser(description="LOCI & Billo CLI Management Tool")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_handover = subparsers.add_parser("handover", help="Retrieve compact handover for session")
    p_handover.add_argument("session_id", type=str)

    p_query = subparsers.add_parser("query", help="Query context entity index")
    p_query.add_argument("query_str", type=str)

    p_compress = subparsers.add_parser("compress", help="Compress text or file via VPS Ollama")
    p_compress.add_argument("target", type=str)

    subparsers.add_parser("health", help="Check system and API health")

    args = parser.parse_args()
    if args.command == "handover":
        cmd_handover(args.session_id)
    elif args.command == "query":
        cmd_query(args.query_str)
    elif args.command == "compress":
        cmd_compress(args.target)
    elif args.command == "health":
        cmd_health()


if __name__ == "__main__":
    main()
