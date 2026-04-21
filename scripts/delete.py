#!/usr/bin/env python3
"""Delete the key or element at a JSON path.

Usage:
    python3 delete.py FILE PATH [--missing-ok]
"""

from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (
    _norm_idx,
    die,
    dump_json,
    format_path,
    load_json,
    parse_path,
    walk_to_parent,
)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Delete the key or element at a JSON path."
    )
    ap.add_argument("file", help="path to JSON file")
    ap.add_argument("path", help="path expression, e.g. users[0].email")
    ap.add_argument(
        "--missing-ok",
        action="store_true",
        help="exit 0 even if the path does not exist",
    )
    args = ap.parse_args()

    data = load_json(args.file)
    try:
        path = parse_path(args.path)
    except ValueError as e:
        die(f"bad path: {e}")

    if not path:
        die("cannot delete root; use a non-empty path")

    try:
        parent, last = walk_to_parent(data, path)
    except (KeyError, IndexError, TypeError) as e:
        if args.missing_ok:
            return
        die(str(e))

    if isinstance(parent, dict):
        if not isinstance(last, str):
            die(
                f"at {format_path(path[:-1])}: object requires string key, "
                f"got {type(last).__name__} {last!r}"
            )
        if last not in parent:
            if args.missing_ok:
                return
            die(f"key {last!r} not found at {format_path(path)}")
        del parent[last]
    elif isinstance(parent, list):
        if not isinstance(last, int):
            die(
                f"at {format_path(path[:-1])}: array requires int index, "
                f"got {type(last).__name__} {last!r}"
            )
        idx = _norm_idx(parent, last)
        if idx is None:
            if args.missing_ok:
                return
            die(
                f"index {last} out of range [-{len(parent)},{len(parent)}) "
                f"at {format_path(path)}"
            )
        del parent[idx]
    else:
        die(
            f"cannot delete from {type(parent).__name__} at "
            f"{format_path(path[:-1])}"
        )

    dump_json(args.file, data)


if __name__ == "__main__":
    main()
