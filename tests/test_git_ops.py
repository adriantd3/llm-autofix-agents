from __future__ import annotations

import subprocess
import unittest
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from llm_autofix_agents.flow.workspace.git import (
    build_temp_branch_name,
    create_temp_branch,
    current_branch,
    delete_branch,
    is_git_repository,
    restore_all_changes,
    restore_original_branch,
)


class GitOpsTests(unittest.TestCase):
    def test_build_temp_branch_name_uses_prefix_timestamp_and_run_id(self) -> None:
        name = build_temp_branch_name(
            run_id="run-20260418T101010Z-abcdef1234",
            branch_prefix="autofix",
            now=datetime(2026, 4, 18, 10, 10, 10, tzinfo=UTC),
        )
        self.assertEqual(name, "autofix/20260418T101010Z-run-20260418T101010Z-abcdef1234")

    def test_create_restore_and_delete_temp_branch(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            self._init_git_repo(repo)

            self.assertTrue(is_git_repository(repo))
            original = current_branch(repo)

            context = create_temp_branch(repo, run_id="run-20260418T110000Z-abcdef1234", branch_prefix="autofix")
            self.assertEqual(context.original_branch, original)
            self.assertNotEqual(context.branch_name, original)
            self.assertEqual(current_branch(repo), context.branch_name)

            restore_original_branch(repo, original_branch=context.original_branch)
            self.assertEqual(current_branch(repo), original)

            delete_branch(repo, branch_name=context.branch_name)
            branches = self._git_output(repo, ["branch", "--list", context.branch_name])
            self.assertEqual(branches.strip(), "")

    def _init_git_repo(self, repo: Path) -> None:
        self._git(repo, ["init", "-b", "main"])
        self._git(repo, ["config", "user.name", "autofix-tests"])
        self._git(repo, ["config", "user.email", "autofix-tests@example.com"])
        (repo / "README.md").write_text("baseline\n", encoding="utf-8")
        self._git(repo, ["add", "README.md"])
        self._git(repo, ["commit", "-m", "init"])

    def _git(self, repo: Path, args: list[str]) -> None:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {completed.stderr}")

    def _git_output(self, repo: Path, args: list[str]) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=str(repo),
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {completed.stderr}")
        return completed.stdout

    def test_restore_all_changes_blocks_on_project_repo(self) -> None:
        import llm_autofix_agents

        project_root = Path(llm_autofix_agents.__file__).resolve().parent.parent
        with self.assertRaises(RuntimeError):
            restore_all_changes(project_root)

    def test_restore_all_changes_allows_override_via_env(self) -> None:
        import llm_autofix_agents

        project_root = Path(llm_autofix_agents.__file__).resolve().parent.parent
        with patch.dict("os.environ", {"AUTOFIX_ALLOW_RESTORE": "1"}):
            with patch("llm_autofix_agents.flow.workspace.git._run_git") as mock_run_git:
                mock_run_git.return_value = subprocess.CompletedProcess(
                    args=["git", "checkout", "--", "."],
                    returncode=0,
                    stdout="",
                    stderr="",
                )
                restore_all_changes(project_root)
                mock_run_git.assert_called()

    def test_restore_all_changes_succeeds_in_isolated_repo(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            repo = Path(tmp_dir)
            self._init_git_repo(repo)
            (repo / "dirty.py").write_text("dirty\n", encoding="utf-8")
            restore_all_changes(repo)
            self.assertFalse((repo / "dirty.py").exists())


if __name__ == "__main__":
    unittest.main()
