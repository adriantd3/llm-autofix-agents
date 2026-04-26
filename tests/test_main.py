from __future__ import annotations

import argparse
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from llm_autofix_agents.contracts import ContainerInstantiation, RunIdentity, RunOutput, RunStatus, StopReason
from llm_autofix_agents.main import _run_run


class MainCliTests(unittest.TestCase):
    def test_run_uses_runtime_repository_and_test_command(self) -> None:
        with TemporaryDirectory() as tmp_dir:
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
                    "llm_autofix_agents.main.ContainerInstantiation.from_env",
                    return_value=ContainerInstantiation(
                        repository=tmp_dir,
                        branch="master",
                        architecture="mono-agent",
                        agent_models={"main": "llama3.1:8b"},
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
                exit_code = _run_run(argparse.Namespace())

            self.assertEqual(exit_code, 0)
            run_input = mocked_run_agent.call_args[0][0]
            self.assertEqual(run_input.target_repo, str(Path(tmp_dir).resolve()))
            self.assertEqual(run_input.test_command, "uv run --with pytest pytest python_testcases/test_gcd.py")


if __name__ == "__main__":
    unittest.main()
