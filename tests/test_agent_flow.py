from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pydantic import SecretStr

from llm_autofix_agents.batch.executor import _run as _run_agent_baseline
from llm_autofix_agents.contracts import ErrorCategory, RunInput, RunStatus, StopReason
from llm_autofix_agents.flow.workspace.git import TempBranchContext
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.llm.settings import LLMSettings, ProviderType
from llm_autofix_agents.observability import ObservabilityConfig
from llm_autofix_agents.tools import build_apr_tools


class AgentFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        tmp_path = Path(self._tmp_dir.name)
        self._observability_config_patcher = patch(
            "llm_autofix_agents.batch.executor.resolve_observability_config",
            return_value=ObservabilityConfig(
                enabled=False,
                interactive=False,
                results_dir=tmp_path / "results",
                sqlite_db_path=tmp_path / "results" / "observability.db",
                live_log_enabled=False,
            ),
        )
        self._git_repo_patcher = patch(
            "llm_autofix_agents.flow.workspace.manager._git.is_git_repository",
            return_value=False,
        )
        self._restore_all_changes_patcher = patch(
            "llm_autofix_agents.flow.workspace.git.restore_all_changes",
        )
        self._observability_config_patcher.start()
        self._git_repo_patcher.start()
        self._restore_all_changes_patcher.start()

    def tearDown(self) -> None:
        self._observability_config_patcher.stop()
        self._git_repo_patcher.stop()
        self._restore_all_changes_patcher.stop()
        self._tmp_dir.cleanup()

    def test_run_agent_baseline_success(self) -> None:
        provider = _CapturingProvider(_proposal(reasoning_summary="suggested fix"))
        with (
            patch(
                "llm_autofix_agents.flow.workspace.state.collect_repo_diff_for_paths",
                return_value="",
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._state.snapshot_repo_state",
                return_value={},
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.detect_untracked_files",
                return_value=[],
            ),
        ):
            output = _run_agent_baseline(
                RunInput(prompt="Fix parser failure"),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.SUCCESS)
        self.assertEqual(output.stop_reason, StopReason.COMPLETED)
        self.assertEqual(output.identity.iteration, 1)
        self.assertIn("stage=agent", output.logs)
        self.assertIn("stage=observability", output.logs)
        self.assertIn("toolset=apr-local", output.logs)
        self.assertIn("tool_profile=full", output.logs)
        self.assertIn("observability_backend=disabled", output.logs)
        self.assertIn("observability", output.artifacts)
        self.assertEqual(output.artifacts["observability"]["backend"], "disabled")
        self.assertIsNotNone(provider.last_user_input)
        assert provider.last_user_input is not None
        self.assertEqual(provider.last_user_input, "Fix parser failure")
        self.assertIsNotNone(provider.last_agent)
        assert provider.last_agent is not None
        self.assertEqual(len(provider.last_agent.tools), len(build_apr_tools("full")))
        self.assertIsNotNone(provider.last_context)
        assert provider.last_context is not None
        self.assertEqual(provider.last_context.root_dir, str(Path(".").resolve()))

    def test_run_agent_baseline_uses_runtime_architecture_metadata(self) -> None:
        provider = _CapturingProvider(_proposal(reasoning_summary="suggested fix"))
        sentinel_architecture = SimpleNamespace(architecture_name="multi_agent_handoff")

        with (
            patch(
                "llm_autofix_agents.batch.executor.build_architecture",
                return_value=sentinel_architecture,
            ) as build_architecture,
            patch("llm_autofix_agents.batch.executor.RunOrchestrator") as orchestrator_cls,
        ):
            orchestrator_cls.return_value.run.return_value = SimpleNamespace(status=RunStatus.SUCCESS)
            output = _run_agent_baseline(
                RunInput(
                    prompt="Fix parser failure",
                    metadata={
                        "runtime_architecture": "multi_agent_handoff",
                        "runtime_agent_models": {"triage": "triage-model"},
                        "tool_profile": "core",
                    },
                ),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.SUCCESS)
        build_architecture.assert_called_once()
        self.assertEqual(build_architecture.call_args.kwargs["strategy"], "multi_agent_handoff")
        self.assertEqual(build_architecture.call_args.kwargs["tool_profile"], "core")
        self.assertEqual(build_architecture.call_args.kwargs["agent_models"], {"triage": "triage-model"})

    def test_run_agent_baseline_stops_on_no_progress(self) -> None:
        provider = _SequencedProvider(
            [_proposal(reasoning_summary="same fix"), _proposal(reasoning_summary="same fix")]
        )
        with (
            _patch_run_test_command(
                side_effect=[
                    SimpleNamespace(
                        exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-baseline"
                    ),
                    SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                    SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                ]
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._state.snapshot_repo_state",
                return_value={"src/a.py": "abc"},
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.detect_untracked_files",
                return_value=[],
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.collect_repo_diff_for_paths",
                return_value="",
            ),
        ):
            output = _run_agent_baseline(
                RunInput(
                    prompt="Fix parser failure",
                    test_command="uv run python -m unittest",
                ),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.PARTIAL)
        self.assertEqual(output.stop_reason, StopReason.NO_PROGRESS)
        self.assertEqual(output.identity.iteration, 2)

    def test_run_agent_baseline_stops_on_max_iterations(self) -> None:
        provider = _SequencedProvider(
            [
                _proposal(reasoning_summary="attempt one"),
                _proposal(reasoning_summary="attempt two"),
                _proposal(reasoning_summary="attempt three"),
            ]
        )
        with (
            _patch_run_test_command(
                side_effect=[
                    SimpleNamespace(
                        exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-baseline"
                    ),
                    SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                    SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                    SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                ]
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._state.snapshot_repo_state",
                side_effect=[
                    {"src/a.py": "v1"},
                    {"src/a.py": "v2"},
                    {"src/a.py": "v2"},
                    {"src/a.py": "v3"},
                    {"src/a.py": "v3"},
                    {"src/a.py": "v4"},
                ],
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.collect_repo_diff_for_paths",
                return_value="diff --git a/src/a.py b/src/a.py",
            ),
        ):
            output = _run_agent_baseline(
                RunInput(
                    prompt="Fix parser failure",
                    test_command="uv run python -m unittest",
                ),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.PARTIAL)
        self.assertEqual(output.stop_reason, StopReason.MAX_ITERATIONS)
        self.assertEqual(output.identity.iteration, 3)

    def test_run_agent_baseline_maps_provider_error(self) -> None:
        output = _run_agent_baseline(
            RunInput(prompt="Fix parser failure"),
            settings=_settings(),
            provider=_FailingProvider(),
        )

        self.assertEqual(output.status, RunStatus.FAILED)
        self.assertEqual(output.stop_reason, StopReason.TOOL_FAILURE)
        self.assertIn("errors", output.artifacts)
        self.assertEqual(len(output.artifacts["errors"]), 1)
        self.assertEqual(output.artifacts["errors"][0]["category"], ErrorCategory.MODEL.value)

    def test_run_agent_baseline_stops_on_regression_detected(self) -> None:
        provider = _SequencedProvider([_proposal(reasoning_summary="introduce breaking change")])
        with (
            _patch_run_test_command(
                side_effect=[
                    SimpleNamespace(exit_code=0, timed_out=False, output="OK", signature="sig-baseline"),
                    SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-last"),
                ]
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._state.snapshot_repo_state",
                side_effect=[
                    {"src/a.py": "v1"},
                    {"src/a.py": "v2"},
                ],
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.collect_repo_diff_for_paths",
                return_value="diff --git a/src/a.py b/src/a.py",
            ),
        ):
            output = _run_agent_baseline(
                RunInput(
                    prompt="Fix parser failure",
                    test_command="uv run python -m unittest",
                ),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.FAILED)
        self.assertEqual(output.stop_reason, StopReason.VALIDATION_FAILURE)
        self.assertIn("errors", output.artifacts)
        self.assertEqual(len(output.artifacts["errors"]), 1)
        self.assertEqual(output.artifacts["errors"][0]["category"], ErrorCategory.VALIDATION.value)
        self.assertIn("validation_result=regression", output.logs)

    def test_run_agent_baseline_no_regression_when_baseline_failing(self) -> None:
        provider = _SequencedProvider([_proposal(reasoning_summary="fix tests")])
        with (
            _patch_run_test_command(
                side_effect=[
                    SimpleNamespace(
                        exit_code=1,
                        timed_out=False,
                        output="FAILED (failures=1)",
                        signature="sig-baseline-fail",
                    ),
                    SimpleNamespace(exit_code=0, timed_out=False, output="OK", signature="sig-now-ok"),
                ]
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._state.snapshot_repo_state",
                side_effect=[
                    {"src/a.py": "v1"},
                    {"src/a.py": "v2"},
                ],
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.collect_repo_diff_for_paths",
                return_value="diff --git a/src/a.py b/src/a.py",
            ),
        ):
            output = _run_agent_baseline(
                RunInput(
                    prompt="Fix parser failure",
                    test_command="uv run python -m unittest",
                ),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.SUCCESS)
        self.assertEqual(output.stop_reason, StopReason.COMPLETED)

    def test_run_agent_baseline_creates_and_deletes_temp_branch_on_success(self) -> None:
        provider = _CapturingProvider(_proposal(reasoning_summary="suggested fix"))
        self._git_repo_patcher.stop()
        with (
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.is_git_repository",
                return_value=True,
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.create_temp_branch",
                return_value=TempBranchContext(
                    branch_name="autofix/20260418T100000Z-run-abc",
                    original_branch="main",
                ),
            ) as create_branch,
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.restore_original_branch",
            ) as restore_branch,
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.delete_branch",
            ) as delete_branch,
            patch(
                "llm_autofix_agents.flow.workspace.state.collect_repo_diff_for_paths",
                return_value="",
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._state.snapshot_repo_state",
                return_value={},
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.detect_untracked_files",
                return_value=[],
            ),
        ):
            output = _run_agent_baseline(
                RunInput(prompt="Fix parser failure"),
                settings=_settings(),
                provider=provider,
            )

        self._git_repo_patcher.start()
        self.assertEqual(output.status, RunStatus.SUCCESS)
        create_branch.assert_called_once()
        restore_branch.assert_called_once()
        delete_branch.assert_called_once()

    def test_run_agent_baseline_keeps_temp_branch_on_validation_failure(self) -> None:
        provider = _SequencedProvider([_proposal(reasoning_summary="attempt one")])
        self._git_repo_patcher.stop()
        with (
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.is_git_repository",
                return_value=True,
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.create_temp_branch",
                return_value=TempBranchContext(
                    branch_name="autofix/20260418T100000Z-run-abc",
                    original_branch="main",
                ),
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.restore_original_branch",
            ) as restore_branch,
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.delete_branch",
            ) as delete_branch,
            _patch_run_test_command(
                side_effect=[
                    SimpleNamespace(exit_code=0, timed_out=False, output="OK", signature="sig-baseline"),
                    SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                ]
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._state.snapshot_repo_state",
                side_effect=[
                    {"src/a.py": "v1"},
                    {"src/a.py": "v2"},
                ],
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.collect_repo_diff_for_paths",
                return_value="diff --git a/src/a.py b/src/a.py",
            ),
        ):
            output = _run_agent_baseline(
                RunInput(
                    prompt="Fix parser failure",
                    test_command="uv run python -m unittest",
                ),
                settings=_settings(),
                provider=provider,
            )

        self._git_repo_patcher.start()
        self.assertEqual(output.status, RunStatus.FAILED)
        restore_branch.assert_called_once()
        delete_branch.assert_not_called()

    def test_run_agent_baseline_fails_when_success_cleanup_fails(self) -> None:
        provider = _CapturingProvider(_proposal(reasoning_summary="suggested fix"))
        self._git_repo_patcher.stop()
        with (
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.is_git_repository",
                return_value=True,
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.create_temp_branch",
                return_value=TempBranchContext(
                    branch_name="autofix/20260418T100000Z-run-abc",
                    original_branch="main",
                ),
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.restore_original_branch",
                side_effect=RuntimeError("cannot switch back"),
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._git.delete_branch",
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.collect_repo_diff_for_paths",
                return_value="",
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._state.snapshot_repo_state",
                return_value={},
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.detect_untracked_files",
                return_value=[],
            ),
        ):
            output = _run_agent_baseline(
                RunInput(prompt="Fix parser failure"),
                settings=_settings(),
                provider=provider,
            )

        self._git_repo_patcher.start()
        self.assertEqual(output.status, RunStatus.FAILED)
        self.assertEqual(output.stop_reason, StopReason.INFRA_FAILURE)
        self.assertIn("errors", output.artifacts)
        self.assertEqual(len(output.artifacts["errors"]), 1)
        self.assertEqual(output.artifacts["errors"][0]["category"], ErrorCategory.INFRA.value)
        self.assertIn("branch_cleanup_error", output.artifacts["errors"][0]["details"])


class _CapturingProvider:
    def __init__(self, response: AgentFixIterationRecord) -> None:
        self._response = response
        self.last_user_input: str | None = None
        self.last_agent: object | None = None
        self.last_context: object | None = None

    async def run_agent(
        self,
        *,
        agent: object,
        user_input: str,
        max_turns: int,
        context: object | None = None,
        hooks: object | None = None,
        event_callback: object | None = None,
    ) -> AgentFixIterationRecord:
        del max_turns, hooks, event_callback
        self.last_user_input = user_input
        self.last_agent = agent
        self.last_context = context
        return self._response


class _FailingProvider:
    async def run_agent(
        self,
        *,
        agent: object,
        user_input: str,
        max_turns: int,
        context: object | None = None,
        hooks: object | None = None,
        event_callback: object | None = None,
    ) -> AgentFixIterationRecord:
        del agent, user_input, max_turns, context, hooks, event_callback
        raise RuntimeError("provider down")


class _SequencedProvider:
    def __init__(self, responses: list[AgentFixIterationRecord]) -> None:
        self._responses = responses
        self._calls = 0

    async def run_agent(
        self,
        *,
        agent: object,
        user_input: str,
        max_turns: int,
        context: object | None = None,
        hooks: object | None = None,
        event_callback: object | None = None,
    ) -> AgentFixIterationRecord:
        del agent, user_input, max_turns, context, hooks, event_callback
        if self._calls >= len(self._responses):
            raise RuntimeError("no more responses configured")
        response = self._responses[self._calls]
        self._calls += 1
        return response


class AgentFlowStatusTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp_dir = tempfile.TemporaryDirectory()
        self._tmp_path = Path(self._tmp_dir.name)
        self._obs_config_patcher = patch(
            "llm_autofix_agents.batch.executor.resolve_observability_config",
            return_value=ObservabilityConfig(
                enabled=False,
                interactive=False,
                results_dir=self._tmp_path / "results",
                sqlite_db_path=self._tmp_path / "results" / "observability.db",
                live_log_enabled=False,
            ),
        )
        self._restore_all_changes_patcher = patch(
            "llm_autofix_agents.flow.workspace.git.restore_all_changes",
        )
        self._obs_config_patcher.start()
        self._restore_all_changes_patcher.start()

    def tearDown(self) -> None:
        self._obs_config_patcher.stop()
        self._restore_all_changes_patcher.stop()
        self._tmp_dir.cleanup()

    @patch("llm_autofix_agents.flow.workspace.manager._git.is_git_repository", return_value=False)
    def test_run_agent_baseline_stops_when_agent_reports_stuck(
        self,
        _is_git_repo: object,
    ) -> None:
        provider = _SequencedProvider([_proposal(reasoning_summary="cannot progress", status="stuck")])
        with (
            _patch_run_test_command(
                side_effect=[
                    SimpleNamespace(
                        exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-baseline"
                    ),
                    SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                ]
            ),
            patch(
                "llm_autofix_agents.flow.workspace.manager._state.snapshot_repo_state",
                side_effect=[
                    {"src/a.py": "v1"},
                    {"src/a.py": "v2"},
                ],
            ),
            patch(
                "llm_autofix_agents.flow.workspace.state.collect_repo_diff_for_paths",
                return_value="diff --git a/src/a.py b/src/a.py",
            ),
        ):
            output = _run_agent_baseline(
                RunInput(
                    prompt="Fix parser failure",
                    test_command="uv run python -m unittest",
                ),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.PARTIAL)
        self.assertEqual(output.stop_reason, StopReason.NO_PROGRESS)
        self.assertIn("iteration_result=agent_reported_stuck", output.logs)


def _proposal(
    *,
    reasoning_summary: str,
    status: str = "done",
    confidence: float = 0.8,
    input_tokens: int = 0,
    output_tokens: int = 0,
    total_tokens: int = 0,
    tool_calls: list[dict[str, str]] | None = None,
) -> AgentFixIterationRecord:
    return AgentFixIterationRecord(
        status=status,
        reasoning_summary=reasoning_summary,
        confidence=confidence,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        tool_calls=tool_calls if tool_calls is not None else [],
    )


def _settings() -> LLMSettings:
    return LLMSettings(
        provider=ProviderType.GEMINI,
        model="gemini-2.5-flash",
        api_key=SecretStr("gemini-key"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        max_turns=3,
        tracing_disabled=True,
        api_max_retries=0,
    )


def _patch_run_test_command(*, side_effect):
    """Patch run_test_command at both import sites used by the flow.

    The first item in side_effect is consumed by the orchestrator baseline test;
    the remaining items are consumed by the iteration runner.

    Both the orchestrator and iteration runner bind run_test_command at import
    time from flow.execution, so each needs its own patch targeting its local
    namespace binding.
    """
    from contextlib import ExitStack

    orchestrator_effect = side_effect[:1]
    runner_effect = side_effect[1:]

    stack = ExitStack()
    stack.enter_context(
        patch("llm_autofix_agents.flow.orchestrator.run_test_command", side_effect=orchestrator_effect)
    )
    stack.enter_context(
        patch("llm_autofix_agents.flow.iteration.runner.run_test_command", side_effect=runner_effect)
    )
    return stack


if __name__ == "__main__":
    unittest.main()
