"""Shared helpers for json-crud scripts.

Path syntax:
    a.b.c              -> ['a', 'b', 'c']
    users[0].name      -> ['users', 0, 'name']
    items[-1]          -> ['items', -1]
    data["weird.key"]  -> ['data', 'weird.key']
    ""                 -> []  (root)
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from typing import Any


def die(msg: str, code: int = 1) -> None:
    print(f"error: {msg}", file=sys.stderr)
    sys.exit(code)


def parse_path(expr: str) -> list:
    if expr == "":
        return []
    result: list = []
    i = 0
    n = len(expr)
    first = True
    while i < n:
        c = expr[i]
        if c == "[":
            i += 1
            if i >= n:
                raise ValueError(f"unclosed '[' at position {i - 1}")
            if expr[i] in ('"', "'"):
                quote = expr[i]
                i += 1
                buf = []
                while i < n and expr[i] != quote:
                    if expr[i] == "\\" and i + 1 < n:
                        buf.append(expr[i + 1])
                        i += 2
                        continue
                    buf.append(expr[i])
                    i += 1
                if i >= n:
                    raise ValueError("unclosed quoted key in path")
                key = "".join(buf)
                i += 1  # skip closing quote
                if i >= n or expr[i] != "]":
                    raise ValueError(f"expected ']' after quoted key at position {i}")
                i += 1
                result.append(key)
            else:
                start = i
                if i < n and expr[i] == "-":
                    i += 1
                while i < n and expr[i].isdigit():
                    i += 1
                num_str = expr[start:i]
                if not num_str or num_str == "-":
                    raise ValueError(f"expected integer inside [] at position {start}")
                if i >= n or expr[i] != "]":
                    raise ValueError(f"expected ']' at position {i}")
                i += 1
                result.append(int(num_str))
            first = False
        elif c == ".":
            if first:
                raise ValueError("unexpected '.' at start of path")
            i += 1
            start = i
            while i < n and expr[i] not in ".[":
                i += 1
            if start == i:
                raise ValueError(f"expected identifier after '.' at position {start}")
            result.append(expr[start:i])
        else:
            if not first:
                raise ValueError(
                    f"expected '.' or '[' at position {i}, got {c!r}"
                )
            start = i
            while i < n and expr[i] not in ".[":
                i += 1
            result.append(expr[start:i])
            first = False
    return result


def format_path(segments: list) -> str:
    if not segments:
        return "<root>"
    parts = []
    for i, seg in enumerate(segments):
        if isinstance(seg, int):
            parts.append(f"[{seg}]")
        else:
            needs_quote = "." in seg or "[" in seg or "]" in seg or seg == ""
            if needs_quote:
                escaped = seg.replace("\\", "\\\\").replace('"', '\\"')
                parts.append(f'["{escaped}"]')
            elif i == 0:
                parts.append(seg)
            else:
                parts.append("." + seg)
    return "".join(parts)


def _norm_idx(arr: list, idx: int) -> int | None:
    n = len(arr)
    if -n <= idx < n:
        return idx if idx >= 0 else idx + n
    return None


def get_value(data: Any, path: list) -> Any:
    current = data
    for i, key in enumerate(path):
        if isinstance(current, dict):
            if not isinstance(key, str):
                raise TypeError(
                    f"at {format_path(path[:i])}: object requires string key, "
                    f"got {type(key).__name__} {key!r}"
                )
            if key not in current:
                raise KeyError(
                    f"key {key!r} not found at {format_path(path[: i + 1])}"
                )
            current = current[key]
        elif isinstance(current, list):
            if not isinstance(key, int):
                raise TypeError(
                    f"at {format_path(path[:i])}: array requires int index, "
                    f"got {type(key).__name__} {key!r}"
                )
            idx = _norm_idx(current, key)
            if idx is None:
                raise IndexError(
                    f"index {key} out of range [-{len(current)},{len(current)}) "
                    f"at {format_path(path[: i + 1])}"
                )
            current = current[idx]
        else:
            raise TypeError(
                f"cannot traverse into {type(current).__name__} "
                f"at {format_path(path[:i])}"
            )
    return current


def walk_to_parent(data: Any, path: list, *, create_parents: bool = False):
    """Walk to the parent of the last segment and return (parent, last_key).

    For set/delete: the last segment need not exist.
    With create_parents=True, missing intermediate containers are created;
    the container type is inferred from the type of the *next* segment
    (int -> list, str -> dict).
    """
    if not path:
        raise ValueError("path is empty; cannot target root with this operation")
    current = data
    for i in range(len(path) - 1):
        key = path[i]
        next_seg = path[i + 1]
        if isinstance(current, dict):
            if not isinstance(key, str):
                raise TypeError(
                    f"at {format_path(path[:i])}: object requires string key, "
                    f"got {type(key).__name__} {key!r}"
                )
            if key not in current:
                if create_parents:
                    current[key] = [] if isinstance(next_seg, int) else {}
                else:
                    raise KeyError(
                        f"key {key!r} not found at {format_path(path[: i + 1])} "
                        f"(use --create-parents to auto-create)"
                    )
            current = current[key]
        elif isinstance(current, list):
            if not isinstance(key, int):
                raise TypeError(
                    f"at {format_path(path[:i])}: array requires int index, "
                    f"got {type(key).__name__} {key!r}"
                )
            idx = _norm_idx(current, key)
            if idx is None:
                if create_parents and key == len(current):
                    new_container = [] if isinstance(next_seg, int) else {}
                    current.append(new_container)
                    current = new_container
                    continue
                raise IndexError(
                    f"index {key} out of range [-{len(current)},{len(current)}) "
                    f"at {format_path(path[: i + 1])}"
                )
            current = current[idx]
        else:
            raise TypeError(
                f"cannot traverse into {type(current).__name__} "
                f"at {format_path(path[:i])}"
            )
    return current, path[-1]


def load_json(path: str) -> Any:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        die(f"file not found: {path}")
    except json.JSONDecodeError as e:
        die(f"invalid JSON in {path}: {e}")


def dump_json(path: str, data: Any) -> None:
    dir_ = os.path.dirname(os.path.abspath(path)) or "."
    fd, tmp = tempfile.mkstemp(prefix=".json_crud.", dir=dir_)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, sort_keys=False)
            f.write("\n")
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
