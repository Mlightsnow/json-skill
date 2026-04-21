# json-crud

A Claude Code **Skill** for safely and efficiently doing CRUD (Create / Read /
Update / Delete) operations on JSON files — especially large ones where
reading the whole file would blow up the agent's context.

## Why

Agents that work with JSON face a dilemma:

- Reading the whole file consumes a lot of tokens and may not even fit.
- Without reading, the agent doesn't know what keys, types, or structure
  the file has, so it can't safely edit specific fields.

`json-crud` solves this with a **two-step workflow**:

1. **Inspect** — run `scripts/inspect.py` to get a compact tree summary:
   types, array lengths, key names, short sample values. Homogeneous
   arrays are collapsed to a single schema. Depth is capped so deep
   structures stay small.
2. **CRUD** — use `scripts/get.py`, `scripts/set.py`, `scripts/delete.py`
   to touch exactly the fields you care about, addressed by path.

The agent-facing documentation lives in [`SKILL.md`](./SKILL.md).

## Install

Clone (or symlink) this repo into your Claude Code skills directory:

```
git clone https://github.com/<you>/json_crud ~/.claude/skills/json-crud
# — or —
ln -s "$(pwd)" ~/.claude/skills/json-crud
```

No dependencies beyond Python 3.8+ stdlib.

## Quickstart

```
python3 scripts/inspect.py examples/sample.json
python3 scripts/inspect.py examples/sample.json --path config.database
python3 scripts/get.py     examples/sample.json 'users[0].name' --raw
python3 scripts/set.py     examples/sample.json 'users[0].name' 'Alicia'
python3 scripts/delete.py  examples/sample.json 'users[0].email'
```

## Command cheatsheet

| Command        | Purpose                                                   |
|----------------|-----------------------------------------------------------|
| `inspect.py`   | Summarize structure (types, sizes, samples)               |
| `get.py`       | Read the value at a path                                  |
| `set.py`       | Create or update the value at a path                      |
| `delete.py`    | Remove the key or array element at a path                 |

Path syntax: `a.b.c` · `users[0].name` · `items[-1]` · `["weird.key"]`.

See [`SKILL.md`](./SKILL.md) for full flags, edge cases, and common pitfalls.

## Run the tests

```
python3 -m unittest tests.test_roundtrip -v
```

## Known limitations

- **JSON only.** JSONL, YAML, TOML are out of scope for v1.
- **Format not preserved.** Writes reformat with `indent=2`; original
  spacing and key order of rewritten subtrees is not retained.
- **No comments / JSON5.** Strict JSON only.
- **Whole-file load.** Very large files (>a few hundred MB) load into
  memory; no streaming.
- **Duplicate keys.** stdlib `json` keeps the last one; we accept this.
- **No file locks.** Writes are atomic (temp file + rename), but there's
  no locking against concurrent writers.

## Roadmap (future work)

- JSONL support (per-line indexing)
- YAML / TOML via optional deps
- Streaming inspector for >1 GB files
- A subset of JSONPath (`$.users[*].name`) for multi-match reads
- Optional JSON Schema emission from `inspect.py`

## Project layout

```
├── README.md                 # (this file)
├── SKILL.md                  # Agent-facing skill doc
├── scripts/
│   ├── _common.py            # Path parser, traversal, atomic I/O
│   ├── inspect.py            # Structure summary
│   ├── get.py                # Read
│   ├── set.py                # Create / update
│   └── delete.py             # Delete
├── examples/
│   └── sample.json           # Demo data exercising all features
└── tests/
    └── test_roundtrip.py     # stdlib unittest
```

## License

MIT (add a LICENSE file as needed).
