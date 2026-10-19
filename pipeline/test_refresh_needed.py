#!/usr/bin/env python3
"""Tests for conservative derived-workflow refresh gating."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from refresh_needed import needs_refresh


class RefreshNeededTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.git("init", "-q")
        self.git("config", "user.email", "ci@example.invalid")
        self.git("config", "user.name", "CI")
        (self.root / "reports").mkdir()
        (self.root / "data").mkdir()
        (self.root / "reports" / "signal-intelligence.json").write_text("{}", encoding="utf-8")
        (self.root / "data" / "upstream.json").write_text("a", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "baseline")

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.root, check=True, capture_output=True)

    def check(self, force=False):
        return needs_refresh(self.root, "reports/signal-intelligence.json", ["data/**"], force)

    def test_no_input_change_skips(self):
        self.assertFalse(self.check()[0])

    def test_unrelated_commit_skips(self):
        (self.root / "README.md").write_text("docs", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "docs")
        self.assertFalse(self.check()[0])

    def test_input_change_recomputes(self):
        (self.root / "data" / "upstream.json").write_text("b", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "data")
        self.assertTrue(self.check()[0])

    def test_force_and_missing_output_recompute(self):
        self.assertTrue(self.check(force=True)[0])
        (self.root / "reports" / "signal-intelligence.json").unlink()
        self.assertTrue(self.check()[0])


if __name__ == "__main__":
    unittest.main()
