from __future__ import annotations

import argparse
import unittest
from contextlib import redirect_stderr
from io import StringIO

from llm_autofix_agents.main import _run_docker_smoke


class MainCliTests(unittest.TestCase):
    def test_run_docker_smoke_returns_2_on_invalid_repo(self) -> None:
        args = argparse.Namespace(repo="missing-dir", command="python --version", image="llm-autofix-runner:py313")
        stderr = StringIO()

        with redirect_stderr(stderr):
            exit_code = _run_docker_smoke(args)

        self.assertEqual(exit_code, 2)
        self.assertIn("repo_path must be an existing directory", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
