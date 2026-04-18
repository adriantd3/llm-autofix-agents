from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from llm_autofix_agents.flow.repo_state import (
    filter_diff_by_ignore_rules,
    load_ignore_rules,
    should_ignore_path,
    snapshot_repo_state,
)


class RepoStateTests(unittest.TestCase):
    def test_load_ignore_rules_includes_autofixignore_entries(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / ".autofixignore").write_text("*.log\ntmp/\n", encoding="utf-8")

            rules = load_ignore_rules(repo)

            self.assertIn("*.log", rules)
            self.assertIn("tmp/", rules)
            self.assertIn("build/", rules)

    def test_snapshot_repo_state_excludes_autofixignore_matches(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            (repo / ".autofixignore").write_text("tmp/\n*.log\n", encoding="utf-8")
            (repo / "src").mkdir(parents=True, exist_ok=True)
            (repo / "src" / "keep.py").write_text("print('ok')\n", encoding="utf-8")
            (repo / "tmp").mkdir(parents=True, exist_ok=True)
            (repo / "tmp" / "ignored.txt").write_text("ignored\n", encoding="utf-8")
            (repo / "debug.log").write_text("ignored\n", encoding="utf-8")

            snapshot = snapshot_repo_state(repo)

            self.assertIn("src/keep.py", snapshot)
            self.assertNotIn("tmp/ignored.txt", snapshot)
            self.assertNotIn("debug.log", snapshot)

    def test_filter_diff_by_ignore_rules_removes_matching_chunks(self) -> None:
        diff = (
            "diff --git a/src/keep.py b/src/keep.py\n"
            "index 111..222 100644\n"
            "--- a/src/keep.py\n"
            "+++ b/src/keep.py\n"
            "@@ -1 +1 @@\n"
            "-old\n"
            "+new\n"
            "\n"
            "diff --git a/build/output.txt b/build/output.txt\n"
            "index 333..444 100644\n"
            "--- a/build/output.txt\n"
            "+++ b/build/output.txt\n"
            "@@ -1 +1 @@\n"
            "-x\n"
            "+y\n"
        )

        filtered = filter_diff_by_ignore_rules(diff, ["build/"])

        self.assertIn("src/keep.py", filtered)
        self.assertNotIn("build/output.txt", filtered)

    def test_should_ignore_path_matches_basename_globs(self) -> None:
        self.assertTrue(should_ignore_path("src/module.pyc", ["*.pyc"]))
        self.assertFalse(should_ignore_path("src/module.py", ["*.pyc"]))


if __name__ == "__main__":
    unittest.main()
