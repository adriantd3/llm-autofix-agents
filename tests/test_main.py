from __future__ import annotations

import argparse
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from llm_autofix_agents.contracts import RunIdentity, RunOutput, RunStatus, StopReason
from llm_autofix_agents.main import _run_agent_smoke, _run_docker_smoke


class MainCliTests(unittest.TestCase):
    def test_run_docker_smoke_returns_2_on_invalid_repo(self) -> None:
        args = argparse.Namespace(repo="missing-dir", command="python --version", image="llm-autofix-runner:py313")
        stderr = StringIO()

        with redirect_stderr(stderr):
            exit_code = _run_docker_smoke(args)

        self.assertEqual(exit_code, 2)
        self.assertIn("repo_path must be an existing directory", stderr.getvalue())

    def test_run_agent_smoke_uses_runtime_repository_and_test_command(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            args = argparse.Namespace(prompt="Analyze a failing test and suggest a minimal fix strategy.")
            output = RunOutput(
                identity=RunIdentity(
                    run_id="run-123",
                    run_fingerprint="0123456789abcdef",
                    iteration=1,
                    iteration_id="run-123-it01",
                ),
                status=RunStatus.SUCCESS,
                stop_reason=StopReason.COMPLETED,
            )
            with (
                patch(
                    "llm_autofix_agents.main.load_container_instantiation_from_env",
                    return_value=argparse.Namespace(
                        repository=tmp_dir,
                        branch="master",
                        architecture="mono-agent",
                        bootstrap_prompt="Fix failing tests with minimal changes.",
                    ),
                ),
                patch(
                    "llm_autofix_agents.main.run_agent_baseline",
                    return_value=output,
                ) as mocked_run_agent,
                patch.dict(
                    "os.environ",
                    {
                        "RUN_TEST_COMMAND": "uv run --with pytest pytest python_testcases/test_gcd.py",
                    },
                    clear=False,
                ),
            ):
                exit_code = _run_agent_smoke(args)

            self.assertEqual(exit_code, 0)
            run_input = mocked_run_agent.call_args[0][0]
            self.assertEqual(run_input.target_repo, str(Path(tmp_dir).resolve()))
            self.assertEqual(run_input.test_command, "uv run --with pytest pytest python_testcases/test_gcd.py")

    def test_run_agent_smoke_returns_2_when_runtime_repository_is_invalid(self) -> None:
        args = argparse.Namespace(prompt="Analyze a failing test and suggest a minimal fix strategy.")
        stderr = StringIO()
        with (
            patch(
                "llm_autofix_agents.main.load_container_instantiation_from_env",
                return_value=argparse.Namespace(
                    repository="not a repo",
                    branch="master",
                    architecture="mono-agent",
                    bootstrap_prompt="Fix failing tests with minimal changes.",
                ),
            ),
            redirect_stderr(stderr),
        ):
            exit_code = _run_agent_smoke(args)

        self.assertEqual(exit_code, 2)
        self.assertIn("RUN_REPOSITORY must be", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
