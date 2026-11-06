#!/usr/bin/env python3
"""Offline learning-cycle demo.

    python -m loci_engine.learning_cli demo --db /tmp/loci-learning.db --out /tmp/trace.json

No network call is made. `--numeric-n` scores that many arithmetic points and
keeps two. That stream is a NUMERICAL_DEMO, not a million agent plans.
"""

from __future__ import annotations

import argparse
import json
import sys

from loci_engine.learning_cycle import run_offline_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LOCI offline learning cycle")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo", help="run the controlled offline mix-weight demo")
    demo.add_argument("--db", required=True, help="scratch or local sqlite path")
    demo.add_argument("--out", help="write the trace JSON here")
    demo.add_argument(
        "--numeric-n",
        type=int,
        default=0,
        help="bounded arithmetic candidates to score (0 skips the stream)",
    )
    demo.add_argument("--trace", help="append-only audit jsonl path")
    args = parser.parse_args(argv)
    if args.command == "demo":
        payload = run_offline_demo(
            args.db,
            numeric_dream_count=max(0, args.numeric_n),
            trace_path=args.trace,
        )
        text = json.dumps(payload, indent=2)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as handle:
                handle.write(text)
                handle.write("\n")
        sys.stdout.write(text)
        sys.stdout.write("\n")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
