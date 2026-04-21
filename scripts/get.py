#!/usr/bin/env python3
"""Read the value at a JSON path.

Usage:
    python3 get.py FILE PATH [--raw]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import die, get_value, load_json, parse_path


def main() -> None:
    ap = argparse.ArgumentParser(description="Read the value at a JSON path.")
    ap.add_argument("file", help="path to JSON file")
    ap.add_argument("path", help="path expression, e.g. users[0].name (empty = root)")
    ap.add_argument(
        "--raw",
        action="store_true",
        help="if the value is a string, print it unquoted",
    )
    args = ap.parse_args()

    data = load_json(args.file)
    try:
        path = parse_path(args.path)
    except ValueError as e:
        die(f"bad path: {e}")
    try:
        value = get_value(data, path)
    except (KeyError, IndexError, TypeError) as e:
        die(str(e))

    if args.raw and isinstance(value, str):
        print(value)
    else:
        print(json.dumps(value, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
