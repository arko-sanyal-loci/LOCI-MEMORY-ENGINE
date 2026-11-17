#!/usr/bin/env python3
"""ethics_categories.py — sudo-required editor for the ETHICS_CAPPED category list.

Usage:
  sudo python3 ethics_categories.py --list
  sudo python3 ethics_categories.py --add <category> <regex>
  sudo python3 ethics_categories.py --remove <category>
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ethics_filter import CATEGORIES_PATH, DEFAULT_CATEGORIES, load_categories

def require_sudo():
    if os.geteuid() != 0: sys.exit("[ethics_categories] run under sudo")

def sh(*a): subprocess.run(list(a), check=False)

def save(cats: dict):
    sh("chflags", "nouchg", str(CATEGORIES_PATH))
    CATEGORIES_PATH.write_text(json.dumps(cats, indent=2, sort_keys=True))
    os.chmod(CATEGORIES_PATH, 0o444)
    sh("chflags", "uchg", str(CATEGORIES_PATH))

def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--list", action="store_true")
    g.add_argument("--add",  nargs=2, metavar=("CATEGORY","REGEX"))
    g.add_argument("--remove", metavar="CATEGORY")
    args = ap.parse_args()

    if not args.list: require_sudo()

    cats = load_categories()
    if args.list:
        print(json.dumps(cats, indent=2, sort_keys=True)); return

    if args.add:
        cat, rx = args.add
        cats.setdefault(cat, []).append(rx)
        save(cats)
        print(f"[ethics_categories] added regex to '{cat}': {rx}")
    elif args.remove:
        if args.remove in cats:
            del cats[args.remove]; save(cats)
            print(f"[ethics_categories] removed '{args.remove}'")
        else:
            print(f"[ethics_categories] no category '{args.remove}'")

if __name__ == "__main__":
    main()
