#!/usr/bin/env python3
"""Set (create or update) the value at a JSON path.

Usage:
    python3 set.py FILE PATH VALUE [--json] [--create-parents]

Without --json, VALUE is stored as a string. With --json, VALUE is parsed as a
JSON literal (number, bool, null, object, array).
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    die,
    dump_json,
    format_path,
    load_json,
    parse_path,
    walk_to_parent,
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Set the value at a JSON path.")
    ap.add_argument("file", help="path to JSON file")
    ap.add_argument("path", help="path expression, e.g. users[0].name")
    ap.add_argument("value", help="value to set (string by default)")
    ap.add_argument(
        "--json",
        action="store_true",
        dest="json_value",
        help="parse VALUE as a JSON literal",
    )
    ap.add_argument(
        "--create-parents",
        action="store_true",
        help="auto-create missing intermediate containers",
    )
    args = ap.parse_args()

    data = load_json(args.file)

    if args.json_value:
        try:
            value = json.loads(args.value)
        except json.JSONDecodeError as e:
            die(f"--json given but VALUE is not valid JSON: {e}")
    else:
        value = args.value

    try:
        path = parse_path(args.path)
    except ValueError as e:
        die(f"bad path: {e}")

    if not path:
        die("cannot set root; use a non-empty path")

    try:
        parent, last = walk_to_parent(
            data, path, create_parents=args.create_parents
        )
    except (KeyError, IndexError, TypeError, ValueError) as e:
        die(str(e))

    if isinstance(parent, dict):
        if not isinstance(last, str):
            die(
                f"at {format_path(path[:-1])}: object requires string key, "
                f"got {type(last).__name__} {last!r}"
            )
        parent[last] = value
    elif isinstance(parent, list):
        if not isinstance(last, int):
            die(
                f"at {format_path(path[:-1])}: array requires int index, "
                f"got {type(last).__name__} {last!r}"
            )
        n = len(parent)
        if -n <= last < n:
            idx = last if last >= 0 else last + n
            parent[idx] = value
        elif last == n:
            parent.append(value)
        else:
            die(
                f"index {last} out of range [-{n},{n}] at {format_path(path)} "
                f"(use index == {n} to append)"
            )
    else:
        die(
            f"cannot set into {type(parent).__name__} at {format_path(path[:-1])}"
        )

    dump_json(args.file, data)


if __name__ == "__main__":
    main()
