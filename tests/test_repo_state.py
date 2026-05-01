from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet
from llm_autofix_agents.flow.policies.validation import validate_iteration
from llm_autofix_agents.flow.workspace.state import (
    detect_workspace_change_set,
    filter_diff_by_ignore_rules,
    load_ignore_rules,
    should_ignore_path,
    snapshot_repo_state,
)
from llm_autofix_agents.llm.provider import AgentFixIterationRecord


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

    @patch("llm_autofix_agents.flow.workspace.state.collect_repo_diff", return_value="diff")
    @patch("llm_autofix_agents.flow.workspace.state.detect_untracked_files", return_value=[])
    def test_detect_workspace_change_set_modified_file(self, _mock_untracked, _mock_diff) -> None:
        repo = Path("/fake/repo")
        before = {"src/a.py": "hash1"}
        after = {"src/a.py": "hash2"}
        changes = detect_workspace_change_set(repo_root=repo, before=before, after=after)
        self.assertEqual(changes.modified_files, ["src/a.py"])
        self.assertEqual(changes.added_files, [])
        self.assertEqual(changes.deleted_files, [])

    @patch("llm_autofix_agents.flow.workspace.state.collect_repo_diff", return_value="")
    @patch("llm_autofix_agents.flow.workspace.state.detect_untracked_files", return_value=["src/new.py"])
    def test_detect_workspace_change_set_new_untracked_file(self, _mock_untracked, _mock_diff) -> None:
        repo = Path("/fake/repo")
        before: dict[str, str] = {}
        after = {"src/new.py": "hash1"}
        changes = detect_workspace_change_set(repo_root=repo, before=before, after=after)
        self.assertEqual(changes.added_files, ["src/new.py"])
        self.assertEqual(changes.untracked_files, ["src/new.py"])
        self.assertEqual(changes.modified_files, [])
        self.assertEqual(changes.deleted_files, [])

    @patch("llm_autofix_agents.flow.workspace.state.collect_repo_diff", return_value="diff")
    @patch("llm_autofix_agents.flow.workspace.state.detect_untracked_files", return_value=[])
    def test_detect_workspace_change_set_deleted_file(self, _mock_untracked, _mock_diff) -> None:
        repo = Path("/fake/repo")
        before = {"src/old.py": "hash1"}
        after: dict[str, str] = {}
        changes = detect_workspace_change_set(repo_root=repo, before=before, after=after)
        self.assertEqual(changes.deleted_files, ["src/old.py"])
        self.assertEqual(changes.modified_files, [])
        self.assertEqual(changes.added_files, [])

    @patch("llm_autofix_agents.flow.workspace.state.collect_repo_diff", return_value="diff")
    @patch("llm_autofix_agents.flow.workspace.state.detect_untracked_files", return_value=[])
    def test_detect_workspace_change_set_diff_excludes_untracked_false_when_no_untracked(self, _mock_untracked, _mock_diff) -> None:
        repo = Path("/fake/repo")
        before = {"src/a.py": "hash1"}
        after = {"src/a.py": "hash2"}
        changes = detect_workspace_change_set(repo_root=repo, before=before, after=after)
        self.assertFalse(changes.diff_excludes_untracked)

    def test_diff_integrity_does_not_trigger_on_untracked_and_empty_diff(self) -> None:
        proposal = AgentFixIterationRecord(
            status="done",
            reasoning_summary="added a new helper",
            confidence=0.8,
        )
        changes = WorkspaceChangeSet(
            modified_files=[],
            added_files=["src/new_helper.py"],
            deleted_files=[],
            untracked_files=["src/new_helper.py"],
            diff="",
            diff_excludes_untracked=True,
        )
        validation = validate_iteration(
            proposal=proposal,
            changes=changes,
            current_test_execution=TestExecution(exit_code=1, timed_out=False, output="fail", signature="sig-now"),
            baseline_test_execution=None,
        )
        self.assertTrue(validation.ok)


if __name__ == "__main__":
    unittest.main()
