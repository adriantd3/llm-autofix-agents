from __future__ import annotations

import argparse
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
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
                patch.dict(
                    "os.environ",
                    {
                        "RUN_REPOSITORY": "https://github.com/jkoppel/QuixBugs.git",
                        "RUN_BRANCH": "master",
                        "RUN_ARCHITECTURE": "mono_agent",
                        "RUN_AGENT_MODELS": '{"main":"llama3.1:8b"}',
                        "RUN_BOOTSTRAP_PROMPT": "Fix failing tests with minimal changes.",
                    },
                    clear=False,
                ),
                patch(
                    "llm_autofix_agents.main.ContainerInstantiation.from_env",
                    return_value=ContainerInstantiation(
                        repository="https://github.com/jkoppel/QuixBugs.git",
                        branch="master",
                        architecture="mono_agent",
                        agent_models={"main": "llama3.1:8b"},
                        bootstrap_prompt="Fix failing tests with minimal changes.",
                    ),
                ),
                patch(
                    "llm_autofix_agents.main.prepare_target_repository",
                    return_value=SimpleNamespace(path=Path(tmp_dir), cleanup=lambda: None),
                ) as mocked_prepare,
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
            mocked_prepare.assert_called_once_with(
                repository="https://github.com/jkoppel/QuixBugs.git",
                branch="master",
            )
            run_input = mocked_run_agent.call_args[0][0]
            self.assertEqual(run_input.target_repo, str(Path(tmp_dir)))
            self.assertEqual(run_input.test_command, "uv run --with pytest pytest python_testcases/test_gcd.py")

    def test_run_fails_fast_when_runtime_contract_is_invalid(self) -> None:
        with (
            patch.dict(
                "os.environ",
                {
                    "RUN_REPOSITORY": "https://github.com/jkoppel/QuixBugs.git",
                    "RUN_BRANCH": "master",
                    "RUN_ARCHITECTURE": "mono_agent",
                    "RUN_AGENT_MODELS": "not-json",
                    "RUN_BOOTSTRAP_PROMPT": "Fix failing tests with minimal changes.",
                },
                clear=False,
            ),
            patch("llm_autofix_agents.main.run_agent_baseline") as mocked_run_agent,
        ):
            exit_code = _run_run(argparse.Namespace())

        self.assertEqual(exit_code, 2)
        mocked_run_agent.assert_not_called()

    def test_run_always_cleans_up_prepared_repository(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            cleanup_probe = SimpleNamespace(cleaned=False)

            def _cleanup() -> None:
                cleanup_probe.cleaned = True

            with (
                patch.dict(
                    "os.environ",
                    {
                        "RUN_REPOSITORY": "https://github.com/jkoppel/QuixBugs.git",
                        "RUN_BRANCH": "master",
                        "RUN_ARCHITECTURE": "mono_agent",
                        "RUN_AGENT_MODELS": '{"main":"llama3.1:8b"}',
                        "RUN_BOOTSTRAP_PROMPT": "Fix failing tests with minimal changes.",
                    },
                    clear=False,
                ),
                patch(
                    "llm_autofix_agents.main.ContainerInstantiation.from_env",
                    return_value=ContainerInstantiation(
                        repository="https://github.com/jkoppel/QuixBugs.git",
                        branch="master",
                        architecture="mono_agent",
                        agent_models={"main": "llama3.1:8b"},
                        bootstrap_prompt="Fix failing tests with minimal changes.",
                    ),
                ),
                patch(
                    "llm_autofix_agents.main.prepare_target_repository",
                    return_value=SimpleNamespace(path=Path(tmp_dir), cleanup=_cleanup),
                ),
                patch(
                    "llm_autofix_agents.main.run_agent_baseline",
                    side_effect=RuntimeError("boom"),
                ),
            ):
                exit_code = _run_run(argparse.Namespace())

        self.assertEqual(exit_code, 1)
        self.assertTrue(cleanup_probe.cleaned)

    def test_run_fails_fast_without_runtime_contract(self) -> None:
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("llm_autofix_agents.main.run_agent_baseline") as mocked_run_agent,
        ):
            exit_code = _run_run(argparse.Namespace())

        self.assertEqual(exit_code, 2)
        mocked_run_agent.assert_not_called()


if __name__ == "__main__":
    unittest.main()
