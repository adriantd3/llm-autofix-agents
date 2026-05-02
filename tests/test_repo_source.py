from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from llm_autofix_agents.repo_source import PreparedRepository, prepare_target_repository


class RepoSourceTests(unittest.TestCase):
    def test_prepare_target_repository_supports_github_slug(self) -> None:
        completed = subprocess.CompletedProcess(args=["git"], returncode=0, stdout="", stderr="")
        with patch("llm_autofix_agents.repo_source.subprocess.run", return_value=completed) as mocked_run:
            prepared = prepare_target_repository(repository="jkoppel/QuixBugs", branch="master")
            command = mocked_run.call_args[0][0]

            self.assertEqual(command[:6], ["git", "clone", "--depth", "1", "--branch", "master"])
            self.assertEqual(command[6], "https://github.com/jkoppel/QuixBugs.git")
            self.assertTrue(prepared.temporary)
            prepared.cleanup()

    def test_prepare_target_repository_rejects_invalid_reference(self) -> None:
        with self.assertRaisesRegex(ValueError, "RUN_REPOSITORY must be"):
            prepare_target_repository(repository="not a repo", branch="master")


if __name__ == "__main__":
    unittest.main()
