"""End-to-end tests for the json-crud scripts.

Run with: python3 -m unittest tests/test_roundtrip.py -v
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
SAMPLE = os.path.join(REPO, "examples", "sample.json")

sys.path.insert(0, SCRIPTS)
from _common import format_path, get_value, parse_path  # noqa: E402


def run(script: str, *args: str):
    cmd = [sys.executable, os.path.join(SCRIPTS, script), *args]
    return subprocess.run(cmd, capture_output=True, text=True)


class PathParserTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_path(""), [])
        self.assertEqual(parse_path("a"), ["a"])
        self.assertEqual(parse_path("a.b.c"), ["a", "b", "c"])
        self.assertEqual(parse_path("users[0].name"), ["users", 0, "name"])
        self.assertEqual(parse_path("items[-1]"), ["items", -1])
        self.assertEqual(parse_path("[0]"), [0])
        self.assertEqual(parse_path("a.b[0][1].c"), ["a", "b", 0, 1, "c"])

    def test_quoted_keys(self):
        self.assertEqual(parse_path('data["weird.key"]'), ["data", "weird.key"])
        self.assertEqual(parse_path('["with space"]'), ["with space"])
        self.assertEqual(parse_path('a["x\\"y"]'), ["a", 'x"y'])

    def test_round_trip_format(self):
        for expr in [
            "a.b.c",
            "users[0].name",
            "items[-1]",
            '["notes.with.dots"]',
        ]:
            self.assertEqual(format_path(parse_path(expr)), expr)

    def test_invalid(self):
        for bad in [".foo", "[abc]", "a.", "a[", "a[0", '["unclosed', "a.[0]b"]:
            with self.assertRaises(ValueError, msg=f"expected error for {bad!r}"):
                parse_path(bad)


class InspectTests(unittest.TestCase):
    def test_root_contains_key_markers(self):
        r = run("inspect.py", SAMPLE)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("root: object(7 keys)", r.stdout)
        self.assertIn("users: array[10] of object(5 keys)", r.stdout)
        self.assertIn("events: array[6] mixed:", r.stdout)
        self.assertIn("[truncated]", r.stdout)  # description is long
        self.assertIn("[depth limit", r.stdout)  # config goes deep

    def test_drill_into_subtree(self):
        r = run("inspect.py", SAMPLE, "--path", "config.database")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("config.database: object", r.stdout)
        self.assertIn("credentials: object(3 keys)", r.stdout)

    def test_invalid_path(self):
        r = run("inspect.py", SAMPLE, "--path", "users[99]")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("out of range", r.stderr)


class CrudTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="json_crud_test_")
        self.file = os.path.join(self.tmpdir, "data.json")
        shutil.copy(SAMPLE, self.file)

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def read(self, path: str):
        with open(self.file, "r", encoding="utf-8") as f:
            return get_value(json.load(f), parse_path(path))

    def test_get_scalar(self):
        r = run("get.py", self.file, "users[0].name")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), '"Alice Walker"')

    def test_get_raw(self):
        r = run("get.py", self.file, "users[0].name", "--raw")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "Alice Walker")

    def test_get_nested_object(self):
        r = run("get.py", self.file, "config.cache")
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual(out["backend"], "redis")

    def test_get_quoted_key(self):
        r = run("get.py", self.file, '["notes.with.dots"]', "--raw")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("This top-level key"))

    def test_set_string(self):
        r = run("set.py", self.file, "version", "3.0.0")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("version"), "3.0.0")
        # Other fields untouched
        self.assertEqual(self.read("users[0].name"), "Alice Walker")

    def test_set_json_value(self):
        r = run("set.py", self.file, "config.cache.ttl_seconds", "900", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("config.cache.ttl_seconds"), 900)

    def test_set_json_object(self):
        r = run(
            "set.py",
            self.file,
            "users[0].meta",
            '{"joined":"2026-01-01","active":false,"tier":"platinum"}',
            "--json",
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("users[0].meta.tier"), "platinum")

    def test_set_append_to_array(self):
        r = run("set.py", self.file, "users[0].roles[2]", "superuser")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("users[0].roles"), ["admin", "owner", "superuser"])

    def test_set_missing_parent_errors_by_default(self):
        r = run("set.py", self.file, "a.b.c", "hi")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--create-parents", r.stderr)

    def test_set_create_parents_dict(self):
        r = run("set.py", self.file, "new.deep.path", "hi", "--create-parents")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("new.deep.path"), "hi")

    def test_set_create_parents_list(self):
        r = run(
            "set.py", self.file, "things[0].name", "first", "--create-parents"
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("things[0].name"), "first")

    def test_delete_key(self):
        r = run("delete.py", self.file, "users[0].email")
        self.assertEqual(r.returncode, 0, r.stderr)
        with self.assertRaises(KeyError):
            self.read("users[0].email")

    def test_delete_array_element(self):
        r = run("delete.py", self.file, "users[0].roles[0]")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("users[0].roles"), ["owner"])

    def test_delete_missing_errors_by_default(self):
        r = run("delete.py", self.file, "nope")
        self.assertNotEqual(r.returncode, 0)

    def test_delete_missing_ok(self):
        r = run("delete.py", self.file, "nope", "--missing-ok")
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_bad_path_syntax(self):
        r = run("get.py", self.file, "a..b")
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("bad path", r.stderr)

    def test_atomic_write_leaves_valid_json(self):
        run("set.py", self.file, "users[0].name", "Zed")
        with open(self.file, "r", encoding="utf-8") as f:
            json.load(f)  # must not raise


if __name__ == "__main__":
    unittest.main()
