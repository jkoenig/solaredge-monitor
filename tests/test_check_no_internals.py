"""Tests for scripts/check_no_internals.sh using a temp repo and temp denylist.

The denylist word is invented; the real denylist is never read here.
"""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "check_no_internals.sh"
WORD = "zebraflux"


class RepoCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.denylist = self.tmp / "denylist"
        self.denylist.write_text(WORD + "\n")
        self.env = dict(os.environ)
        for key in [k for k in self.env if k.startswith("GIT_")]:
            del self.env[key]
        self.env.update({
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "Test Author",
            "GIT_AUTHOR_EMAIL": "author@example.invalid",
            "GIT_COMMITTER_NAME": "Test Committer",
            "GIT_COMMITTER_EMAIL": "committer@example.invalid",
            "INTERNALS_DENYLIST": str(self.denylist),
        })
        self.git("init", "-q")

    def git(self, *args, env=None):
        r = subprocess.run(
            ["git", *args], cwd=str(self.repo), env=env or self.env,
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout.strip()

    def commit(self, message, env=None):
        self.git("commit", "-q", "--allow-empty", "-m", message, env=env)
        return self.git("rev-parse", "HEAD")

    MODE = "--history"

    def scan(self):
        return subprocess.run(
            ["bash", str(SCRIPT), self.MODE, "--require-denylist"],
            cwd=str(self.repo), env=self.env,
            capture_output=True, text=True, timeout=60,
        )

    def assert_no_leak(self, r):
        self.assertNotIn(WORD, (r.stdout + r.stderr).lower())


class TreeScanTest(RepoCase):
    MODE = "--tree"

    def write(self, name, data):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data)

    def add_commit(self, *names):
        self.git("add", "--", *names)
        self.git("commit", "-q", "-m", "add files")

    def test_clean_tree(self):
        self.write("a.txt", "nothing special\n")
        self.add_commit("a.txt")
        self.write("new.txt", "also harmless\n")
        r = self.scan()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "CLEAN")

    def test_tracked_hit_prints_path_only(self):
        self.write("a.txt", "line with %s inside\n" % WORD.upper())
        self.add_commit("a.txt")
        r = self.scan()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assert_no_leak(r)
        self.assertEqual(r.stdout.splitlines(), ["a.txt", "HITS: 1"])

    def test_untracked_text_and_binary_hits_print_path_only(self):
        self.write("a.txt", "clean\n")
        self.add_commit("a.txt")
        self.write("notes/new file.txt", "some %s here\n" % WORD)
        self.write("img.bin", b"\x89PNG\x00\x01" + WORD.encode() + b"\x00\xff")
        self.write("fine.txt", "clean too\n")
        r = self.scan()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assert_no_leak(r)
        self.assertEqual(
            sorted(r.stdout.splitlines()),
            ["HITS: 2", "untracked: img.bin", "untracked: notes/new file.txt"])

    def test_ignored_files_and_the_denylist_are_not_reported(self):
        self.write(".gitignore", "private.txt\n")
        self.add_commit(".gitignore")
        self.write("private.txt", "%s\n" % WORD)
        # a denylist inside the repo that is not ignored must not hit itself
        inside = self.repo / "list.local"
        inside.write_text(WORD + "\n")
        self.env["INTERNALS_DENYLIST"] = str(inside)
        r = self.scan()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "CLEAN")

    def test_header_documents_the_scan_limits(self):
        text = SCRIPT.read_text()
        self.assertIn("What --tree does NOT scan", text)
        self.assertIn("tracked binary files", text)


class HistoryScanTest(RepoCase):
    def test_clean_history(self):
        self.commit("first\n\nnothing special here")
        r = self.scan()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip(), "CLEAN")

    def test_message_hit_prints_hash_only(self):
        clean = self.commit("first\n\nnothing special here")
        # body line starting with the word, and one with the word mid-line
        first = self.commit("second\n\n%s starts this body line\nmore text" % WORD)
        mid = self.commit("third\n\nintro line\nsome %s inside" % WORD.upper())
        r = self.scan()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assert_no_leak(r)
        lines = r.stdout.splitlines()
        self.assertIn("commit-message/author: %s" % first, lines)
        self.assertIn("commit-message/author: %s" % mid, lines)
        self.assertNotIn("commit-message/author: %s" % clean, lines)
        self.assertEqual(lines[-1], "HITS: 2")

    def test_author_hit_prints_hash_only(self):
        env = dict(self.env)
        env["GIT_AUTHOR_NAME"] = "Some %s Person" % WORD
        h = self.commit("harmless message", env=env)
        r = self.scan()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assert_no_leak(r)
        self.assertEqual(
            r.stdout.splitlines(), ["commit-message/author: %s" % h, "HITS: 1"])

    def test_tag_message_hit_prints_tag_name_only(self):
        self.commit("first")
        self.git("tag", "-a", "v-test", "-m", "note\n\n%s in a tag message" % WORD)
        r = self.scan()
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assert_no_leak(r)
        self.assertEqual(
            r.stdout.splitlines(), ["tag: refs/tags/v-test", "HITS: 1"])


if __name__ == "__main__":
    unittest.main()
