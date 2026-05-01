from __future__ import annotations

import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from llm_autofix_agents.contracts import RunInput
from llm_autofix_agents.flow.agent_execution import AgentExecutionResult
from llm_autofix_agents.flow.iteration.runner import IterationRunner
from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.llm.settings import LLMSettings, ProviderType
from llm_autofix_agents.observability.telemetry_models import IterationTelemetryResult
from llm_autofix_agents.tools.context import APRToolContext


class IterationRunnerTests(unittest.TestCase):
    def test_run_records_logs_and_returns_none_when_not_terminal(self) -> None:
        agent_runner = _CapturingAgentRunner()
        workspace = _StubWorkspaceManager(
            changes=WorkspaceChangeSet(
                modified_files=[],
                added_files=[],
                deleted_files=[],
                untracked_files=[],
                diff="",
                diff_excludes_untracked=False,
            )
        )
        telemetry = _StubRunTelemetry()
        cfg = _build_config(telemetry=telemetry)
        state = RunState()

        test_execution = TestExecution(
            exit_code=1,
            timed_out=False,
            output="FAILED (failures=1)",
            signature="sig-1",
        )

        runner = IterationRunner(
            agent_runner=agent_runner,
            workspace=workspace,
            output_builder=_StubOutputBuilder(),
        )

        with patch(
            "llm_autofix_agents.flow.execution.tests.run_test_command",
            return_value=test_execution,
        ):
            output = runner.run(
                run_input=RunInput(prompt="Fix parser failure", test_command="pytest"),
                cfg=cfg,
                state=state,
                iteration=1,
            )

        self.assertIsNone(output)
        self.assertIsNotNone(agent_runner.last_context)
        assert agent_runner.last_context is not None
        self.assertEqual(agent_runner.last_context.user_input, "Fix parser failure")
        self.assertIn("stage=agent", state.accumulated_logs)
        self.assertIn("changed_files=0", state.accumulated_logs)
        self.assertIsNotNone(state.latest_tests)
        assert state.latest_tests is not None
        self.assertEqual(state.latest_tests.failed, 1)
        self.assertTrue(telemetry.iteration_telemetry.finish_called)
        self.assertEqual(telemetry.iteration_telemetry.test_execution_calls, 1)


@dataclass
class _StubOutputBuilder:
    def validation_failure(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - should not be called
        raise AssertionError("validation_failure should not be called")

    def branch_cleanup_failed(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - should not be called
        raise AssertionError("branch_cleanup_failed should not be called")

    def build(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - should not be called
        raise AssertionError("build should not be called")


class _CapturingAgentRunner:
    def __init__(self) -> None:
        self.last_context = None

    def run_agent(self, *, context, execution_index, provider_call):
        del execution_index, provider_call
        self.last_context = context
        proposal = AgentFixIterationRecord(
            status="in_progress",
            reasoning_summary="attempt",
            confidence=0.2,
        )
        return AgentExecutionResult(
            proposal=proposal,
            agent_execution_id="agent-1",
            tool_calls_count=0,
        )


class _StubWorkspaceManager:
    def __init__(self, *, changes: WorkspaceChangeSet) -> None:
        self._changes = changes

    def snapshot(self, cfg: RunConfig) -> dict[str, str]:
        return {}

    def ensure_temp_branch_for_first_iteration(self, *, cfg: RunConfig, iteration: int, logs: list[str]) -> None:
        return None

    def inspect_changes(self, *, cfg: RunConfig, before_snapshot: dict[str, str]) -> WorkspaceChangeSet:
        return self._changes

    def restore_temp_branch_for_debug(self, *, cfg: RunConfig, logs: list[str]) -> None:
        return None

    def cleanup_temp_branch_after_success(self, cfg: RunConfig) -> str | None:
        return None


class _StubIterationTelemetry:
    def __init__(self) -> None:
        self.finish_called = False
        self.test_execution_calls = 0
        self.finished_result: IterationTelemetryResult | None = None

    def record_test_execution(self, **kwargs: Any) -> None:
        self.test_execution_calls += 1

    def record_file_changes(self, **kwargs: Any) -> None:
        return None

    def finish_iteration(self, *, result: IterationTelemetryResult) -> None:
        self.finish_called = True
        self.finished_result = result


class _StubRunTelemetry:
    def __init__(self) -> None:
        self.iteration_telemetry = _StubIterationTelemetry()

    def start_iteration(self, *, iteration_id: str, iteration_index: int):
        return self.iteration_telemetry


def _build_config(*, telemetry: _StubRunTelemetry) -> RunConfig:
    settings = LLMSettings(provider=ProviderType.OLLAMA, model="test")
    return RunConfig(
        run_id="run-123",
        run_agent_id="agent-123",
        architecture_name="mono_agent",
        settings=settings,
        provider=_StubProvider(),
        facade_agent_builder=lambda: object(),
        agent_context=APRToolContext(root_dir=str(Path(".").resolve())),
        tool_profile="full",
        tool_count=0,
        max_iterations=3,
        test_timeout_seconds=120,
        repo_root=Path("."),
        telemetry=telemetry,
        sqlite_store=None,
        live_observer=None,
        run_input_metadata={},
        agent_config={},
        run_started_monotonic=0.0,
        baseline_test_execution=None,
        temp_branch=None,
    )


class _StubProvider:
    async def run_agent(self, **kwargs: Any):
        raise AssertionError("Provider should not be called in this test")


if __name__ == "__main__":
    unittest.main()
