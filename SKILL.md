---
name: json-crud
description: "Use this skill to read, create, update, or delete fields inside JSON files — especially when the JSON is large enough that reading the whole file would burn context. The workflow is two-step: first run inspect.py for a compact structure summary (keys, types, array lengths, sample values), then use get.py / set.py / delete.py to touch only the fields you care about."
---

# json-crud

## When to use

- You need to CRUD a JSON file and reading it whole would waste context.
- You don't know the JSON's structure yet — use `inspect.py` first.
- You want safe, atomic edits to a specific field without reformatting the rest.

## When NOT to use

- The JSON is small (<50 lines) — just `Read` it.
- You need to rewrite or restructure the whole file — use `Read` + `Write`.
- The file is JSONL / YAML / TOML — not supported in v1.

## Workflow

```
1. python3 scripts/inspect.py FILE                       # top-level shape
2. python3 scripts/inspect.py FILE --path SUBPATH        # drill deeper as needed
3. python3 scripts/get.py FILE PATH                      # confirm current value
4. python3 scripts/set.py FILE PATH VALUE                # or delete.py
5. python3 scripts/get.py FILE PATH                      # verify the write
```

The scripts are self-contained Python 3 stdlib (no pip install).
Invoke them with `python3 scripts/<name>.py` from the skill directory, or add
`scripts/` to your `$PATH`.

## Path syntax

| Example                  | Meaning                                     |
|--------------------------|---------------------------------------------|
| `""`                     | Root                                        |
| `version`                | Top-level string key `version`              |
| `users[0].name`          | `name` of the 0th element of `users`        |
| `items[-1]`              | Last element of `items`                     |
| `config.db.host`         | Nested path                                 |
| `["weird.key"]`          | Root key containing a literal dot           |
| `data["a.b"]`            | Nested key containing a literal dot         |
| `[0].foo`                | If the root is an array                     |

**Quote brackets in your shell:** `'users[0].name'` (single quotes) avoids
glob expansion.

## Commands

### `inspect.py` — structure summary

```
python3 scripts/inspect.py FILE [--path P] [--depth N]
                                [--sample-strings N] [--array-samples K]
                                [--max-object-keys N]
```

| Flag                  | Default | What it does                                |
|-----------------------|---------|---------------------------------------------|
| `--path P`            | root    | Summarize the subtree at `P`                |
| `--depth N`           | 3       | Max nesting depth before `[depth limit]`    |
| `--sample-strings N`  | 40      | Truncate string samples to N chars          |
| `--array-samples K`   | 1       | Expand K sample elements of each array      |
| `--max-object-keys N` | 20      | Collapse objects with more than N keys      |

Output is a compact tree. Homogeneous object-arrays are collapsed to one
`[sample #0]` schema instead of N repetitions. `[depth limit]` lines suggest
the exact `--path` to drill into.

### `get.py` — read a value

```
python3 scripts/get.py FILE PATH [--raw]
```

Prints the value at `PATH` as JSON. `--raw` prints strings unquoted
(useful for piping into other tools, like `jq -r`).

### `set.py` — create or update

```
python3 scripts/set.py FILE PATH VALUE [--json] [--create-parents]
```

- Without `--json`, `VALUE` is stored as a string.
- With `--json`, `VALUE` is parsed as a JSON literal: number, bool, null,
  object, or array. Example: `set.py f cfg.enabled true --json`.
- By default, missing intermediate containers raise an error. Use
  `--create-parents` to auto-create them (type is inferred from the next
  path segment: int → array, string → object).
- For arrays, `PATH ending in [len]` appends a new element.

### `delete.py` — remove

```
python3 scripts/delete.py FILE PATH [--missing-ok]
```

Removes the key or array element at `PATH`. `--missing-ok` makes the
operation idempotent (exit 0 even if the path didn't exist).

## Common pitfalls

- **Shell globbing of brackets**: wrap paths in single quotes:
  `'users[0].name'`, not `users[0].name`.
- **String vs JSON values**: `set.py f k 1` stores the **string** `"1"`.
  For the **number** `1`, use `set.py f k 1 --json`.
- **Reformatted whitespace**: writes go back with `indent=2`. Original
  spacing / ordering of keys that were rewritten is not preserved.
- **No comments / JSON5**: strict JSON only.
- **Integer-string keys**: `.0` or `["0"]` is a string key; `[0]` is an
  array index.

## Example

```
$ python3 scripts/inspect.py examples/sample.json
root: object(7 keys)
├─ version: str(5) = "2.1.0"
├─ users: array[10] of object(5 keys)
│  └─ [sample #0]
│     ├─ id: int = 1
│     ├─ name: str(12) = "Alice Walker"
│     ...
└─ config: object(4 keys)
   ├─ database: object(4 keys)
   ...

$ python3 scripts/get.py examples/sample.json 'users[0].name' --raw
Alice Walker

$ python3 scripts/set.py examples/sample.json 'users[0].name' 'Alicia'
$ python3 scripts/get.py examples/sample.json 'users[0].name' --raw
Alicia
```

## Testing

```
python3 -m unittest tests.test_roundtrip -v
```

All tests use stdlib only.
