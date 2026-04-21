#!/usr/bin/env python3
"""Scan a JSON file and emit a compact structure summary.

Usage:
    python3 inspect.py FILE [--path P] [--depth N] [--sample-strings N] [--array-samples K]
"""

from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import die, format_path, get_value, load_json, parse_path

GLYPH_MID = "├─ "
GLYPH_LAST = "└─ "
CONT_MID = "│  "
CONT_LAST = "   "


def type_name(x) -> str:
    if x is None:
        return "null"
    if isinstance(x, bool):
        return "bool"
    if isinstance(x, int):
        return "int"
    if isinstance(x, float):
        return "float"
    if isinstance(x, str):
        return "str"
    if isinstance(x, list):
        return "array"
    if isinstance(x, dict):
        return "object"
    return type(x).__name__


def scalar_inline(x, string_limit: int) -> str:
    """One-line summary for a scalar, e.g. `str = "abc"` or `int = 1`."""
    tn = type_name(x)
    if x is None:
        return "null"
    if isinstance(x, bool):
        return f"bool = {'true' if x else 'false'}"
    if isinstance(x, (int, float)):
        return f"{tn} = {json.dumps(x)}"
    if isinstance(x, str):
        if len(x) <= string_limit:
            return f'str({len(x)}) = {json.dumps(x, ensure_ascii=False)}'
        head = json.dumps(x[:string_limit], ensure_ascii=False)
        return f'str(len={len(x)}) = {head[:-1]}…"  [truncated]'
    return f"{tn}"


def homogeneous_schema(items: list):
    """Return a canonical key-set / type signature if items are 'same-shape',
    else None.
    """
    if not items:
        return None
    first = items[0]
    if isinstance(first, dict):
        keyset = tuple(sorted(first.keys()))
        for x in items[1:]:
            if not isinstance(x, dict) or tuple(sorted(x.keys())) != keyset:
                return None
        return ("object", keyset)
    t = type_name(first)
    for x in items[1:]:
        if type_name(x) != t:
            return None
    return ("scalar", t)


def render(
    label: str,
    node,
    *,
    depth_left: int,
    string_limit: int,
    array_samples: int,
    max_object_keys: int,
    path_so_far: list,
    prefix: str = "",
    is_root: bool = False,
    is_last: bool = True,
) -> list:
    """Render `node` as a list of lines, beginning with its header line."""
    lines = []
    connector = "" if is_root else (GLYPH_LAST if is_last else GLYPH_MID)
    header_prefix = prefix + connector

    # --- scalar ---
    if not isinstance(node, (dict, list)):
        lines.append(f"{header_prefix}{label}: {scalar_inline(node, string_limit)}")
        return lines

    # --- dict ---
    if isinstance(node, dict):
        n = len(node)
        header = f"{header_prefix}{label}: object({n} key{'s' if n != 1 else ''})"
        if n == 0 or depth_left <= 0:
            if n > 0 and depth_left <= 0:
                header += f"  [depth limit — use --path {format_path(path_so_far)}]"
            lines.append(header)
            return lines
        lines.append(header)
        keys = list(node.keys())
        show_keys = keys[:max_object_keys]
        child_cont = CONT_LAST if is_last and not is_root else CONT_MID
        if is_root:
            child_cont = ""
        for i, k in enumerate(show_keys):
            is_child_last = (i == len(show_keys) - 1) and (len(keys) == len(show_keys))
            lines.extend(
                render(
                    k,
                    node[k],
                    depth_left=depth_left - 1,
                    string_limit=string_limit,
                    array_samples=array_samples,
                    max_object_keys=max_object_keys,
                    path_so_far=path_so_far + [k],
                    prefix=prefix + child_cont if not is_root else "",
                    is_last=is_child_last,
                )
            )
        if len(keys) > len(show_keys):
            more = len(keys) - len(show_keys)
            lines.append(
                f"{prefix}{child_cont if not is_root else ''}{GLYPH_LAST}... +{more} more key(s)"
            )
        return lines

    # --- list ---
    if isinstance(node, list):
        n = len(node)
        if n == 0:
            lines.append(f"{header_prefix}{label}: array[0]")
            return lines
        schema = homogeneous_schema(node)
        child_cont = CONT_LAST if is_last and not is_root else CONT_MID
        if is_root:
            child_cont = ""

        if schema is None:
            types = sorted({type_name(x) for x in node})
            header = f"{header_prefix}{label}: array[{n}] mixed: [{', '.join(types)}]"
            if depth_left <= 0:
                header += f"  [depth limit — use --path {format_path(path_so_far)}]"
                lines.append(header)
                return lines
            lines.append(header)
            # Sample up to array_samples items
            show = min(array_samples, n)
            for i in range(show):
                is_child_last = i == show - 1
                lines.extend(
                    render(
                        f"[{i}]",
                        node[i],
                        depth_left=depth_left - 1,
                        string_limit=string_limit,
                        array_samples=array_samples,
                        max_object_keys=max_object_keys,
                        path_so_far=path_so_far + [i],
                        prefix=prefix + (child_cont if not is_root else ""),
                        is_last=is_child_last,
                    )
                )
            return lines

        kind, info = schema
        if kind == "scalar":
            lines.append(f"{header_prefix}{label}: array[{n}] of {info}")
            return lines

        # Homogeneous objects
        key_count = len(info)
        header = f"{header_prefix}{label}: array[{n}] of object({key_count} key{'s' if key_count != 1 else ''})"
        if depth_left <= 0:
            header += f"  [depth limit — use --path {format_path(path_so_far + [0])}]"
            lines.append(header)
            return lines
        lines.append(header)
        show = min(array_samples, n)
        for i in range(show):
            is_child_last = i == show - 1
            sample_prefix = prefix + (child_cont if not is_root else "")
            lines.append(
                f"{sample_prefix}{GLYPH_LAST if is_child_last else GLYPH_MID}[sample #{i}]"
            )
            inner_cont = CONT_LAST if is_child_last else CONT_MID
            obj = node[i]
            obj_keys = list(obj.keys())
            shown = obj_keys[:max_object_keys]
            for j, k in enumerate(shown):
                is_k_last = (j == len(shown) - 1) and (len(obj_keys) == len(shown))
                lines.extend(
                    render(
                        k,
                        obj[k],
                        depth_left=depth_left - 1,
                        string_limit=string_limit,
                        array_samples=array_samples,
                        max_object_keys=max_object_keys,
                        path_so_far=path_so_far + [i, k],
                        prefix=sample_prefix + inner_cont,
                        is_last=is_k_last,
                    )
                )
            if len(obj_keys) > len(shown):
                more = len(obj_keys) - len(shown)
                lines.append(
                    f"{sample_prefix}{inner_cont}{GLYPH_LAST}... +{more} more key(s)"
                )
        return lines

    lines.append(f"{header_prefix}{label}: {type_name(node)}")
    return lines


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Scan a JSON file and emit a compact structure summary."
    )
    ap.add_argument("file", help="path to JSON file")
    ap.add_argument("--path", default="", help="drill into a subtree (default: root)")
    ap.add_argument("--depth", type=int, default=3, help="max nesting depth (default: 3)")
    ap.add_argument(
        "--sample-strings",
        type=int,
        default=40,
        dest="string_limit",
        help="max chars of string samples before truncation (default: 40)",
    )
    ap.add_argument(
        "--array-samples",
        type=int,
        default=1,
        help="number of array elements to expand as samples (default: 1)",
    )
    ap.add_argument(
        "--max-object-keys",
        type=int,
        default=20,
        help="max keys shown per object before collapsing (default: 20)",
    )
    args = ap.parse_args()

    data = load_json(args.file)
    try:
        path = parse_path(args.path)
    except ValueError as e:
        die(f"bad path: {e}")
    try:
        node = get_value(data, path)
    except (KeyError, IndexError, TypeError) as e:
        die(str(e))

    label = "root" if not path else format_path(path)
    lines = render(
        label,
        node,
        depth_left=args.depth,
        string_limit=args.string_limit,
        array_samples=args.array_samples,
        max_object_keys=args.max_object_keys,
        path_so_far=path,
        is_root=True,
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
