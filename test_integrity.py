import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import integrity

SCRIPT = str(Path(integrity.__file__).resolve())


class TempFolderTestCase(unittest.TestCase):
    """Base class: gives every test its own empty temporary folder."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def write(self, relative, data=b"hello"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path


class TestHashFile(TempFolderTestCase):
    def test_known_hash_of_hello(self):
        path = self.write("a.txt", b"hello")
        self.assertEqual(
            integrity.hash_file(path),
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824",
        )

    def test_empty_file(self):
        path = self.write("empty.txt", b"")
        self.assertEqual(
            integrity.hash_file(path),
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_large_file_matches_hashing_all_at_once(self):
        # Bigger than one chunk, so the chunk loop runs several times
        data = b"a" * (integrity.CHUNK_SIZE * 2 + 123)
        path = self.write("big.bin", data)
        self.assertEqual(integrity.hash_file(path), hashlib.sha256(data).hexdigest())

    def test_one_byte_change_changes_hash(self):
        first = integrity.hash_file(self.write("a.txt", b"hello"))
        second = integrity.hash_file(self.write("a.txt", b"Hello"))
        self.assertNotEqual(first, second)


class TestScanFolder(TempFolderTestCase):
    def test_finds_nested_files_with_forward_slash_paths(self):
        self.write("a.txt")
        self.write("sub/deep/b.txt")
        hashes = integrity.scan_folder(self.root)
        self.assertEqual(set(hashes), {"a.txt", "sub/deep/b.txt"})

    def test_skips_ignored_folders(self):
        self.write("a.txt")
        self.write("venv/lib.py")
        self.write(".git/config")
        self.write("__pycache__/x.pyc")
        self.assertEqual(set(integrity.scan_folder(self.root)), {"a.txt"})

    def test_skips_the_baseline_file_itself(self):
        self.write("a.txt")
        self.write(integrity.BASELINE_FILE, b"{}")
        self.assertEqual(set(integrity.scan_folder(self.root)), {"a.txt"})

    def test_empty_folder(self):
        self.assertEqual(integrity.scan_folder(self.root), {})


class TestBaselineFile(TempFolderTestCase):
    def test_save_then_load_round_trip(self):
        target = str(self.root / "base.json")
        data = {"a.txt": "abc", "sub/b.txt": "def"}
        integrity.save_baseline(data, target)
        self.assertEqual(integrity.load_baseline(target), data)

    def test_missing_baseline_returns_none(self):
        self.assertIsNone(integrity.load_baseline(str(self.root / "nope.json")))

    def test_corrupt_baseline_returns_none(self):
        path = self.write("bad.json", b"{ this is not json")
        self.assertIsNone(integrity.load_baseline(str(path)))


class TestCompare(unittest.TestCase):
    def test_no_changes(self):
        base = {"a": "h1", "b": "h2"}
        self.assertEqual(integrity.compare(base, dict(base)), ([], [], [], []))

    def test_modified(self):
        added, modified, deleted, renamed = integrity.compare({"a": "h1"}, {"a": "h2"})
        self.assertEqual((added, modified, deleted, renamed), ([], ["a"], [], []))

    def test_added(self):
        added, modified, deleted, renamed = integrity.compare({"a": "h1"}, {"a": "h1", "b": "h2"})
        self.assertEqual((added, modified, deleted, renamed), (["b"], [], [], []))

    def test_deleted(self):
        added, modified, deleted, renamed = integrity.compare({"a": "h1", "b": "h2"}, {"a": "h1"})
        self.assertEqual((added, modified, deleted, renamed), ([], [], ["b"], []))

    def test_rename_is_detected(self):
        added, modified, deleted, renamed = integrity.compare({"b.txt": "h2"}, {"renamed.txt": "h2"})
        self.assertEqual((added, modified, deleted), ([], [], []))
        self.assertEqual(renamed, [("b.txt", "renamed.txt")])

    def test_rename_plus_edit_shows_as_added_and_deleted(self):
        # Known limit: contents changed too, so the hashes no longer match
        added, modified, deleted, renamed = integrity.compare({"b.txt": "h2"}, {"other.txt": "h3"})
        self.assertEqual((added, deleted, renamed), (["other.txt"], ["b.txt"], []))

    def test_extra_copy_of_a_file_is_added_not_renamed_twice(self):
        # x was renamed to y, and z is a brand-new copy with the same content
        added, modified, deleted, renamed = integrity.compare({"x": "h"}, {"y": "h", "z": "h"})
        self.assertEqual(renamed, [("x", "y")])
        self.assertEqual(added, ["z"])
        self.assertEqual(deleted, [])

    def test_two_identical_deleted_files_only_one_is_renamed(self):
        added, modified, deleted, renamed = integrity.compare({"x": "h", "y": "h"}, {"z": "h"})
        self.assertEqual(len(renamed), 1)
        self.assertEqual(added, [])
        self.assertEqual(len(deleted), 1)


class TestCommandLine(TempFolderTestCase):
    """Runs the real program, so we also test the exit codes."""

    def run_tool(self, *args):
        return subprocess.run(
            [sys.executable, SCRIPT, *args],
            cwd=self.root, capture_output=True, text=True,
        )

    def test_check_with_no_changes_exits_0(self):
        self.write("data/a.txt")
        self.run_tool("baseline", "data")
        result = self.run_tool("check", "data")
        self.assertEqual(result.returncode, 0)
        self.assertIn("OK", result.stdout)

    def test_check_after_tampering_exits_1(self):
        self.write("data/a.txt", b"hello")
        self.run_tool("baseline", "data")
        self.write("data/a.txt", b"tampered")
        result = self.run_tool("check", "data")
        self.assertEqual(result.returncode, 1)
        self.assertIn("[MODIFIED] a.txt", result.stdout)

    def test_check_without_baseline_gives_helpful_message(self):
        self.write("data/a.txt")
        result = self.run_tool("check", "data")
        self.assertIn("No usable", result.stdout)


if __name__ == "__main__":
    unittest.main()