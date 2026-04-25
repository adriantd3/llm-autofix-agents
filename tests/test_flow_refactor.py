from __future__ import annotations

import unittest

from llm_autofix_agents.contracts import ErrorCategory, RunInput, RunStatus, StopReason, build_run_identity
from llm_autofix_agents.flow.errors import ProviderExecutionError, WorkspaceError, error_category_from_exception
from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet
from llm_autofix_agents.flow.policies.validation import validate_iteration
from llm_autofix_agents.flow.runtime.context import RunState
from llm_autofix_agents.llm.provider import AgentFixIterationRecord


class FlowRefactorTests(unittest.TestCase):
    def test_validate_iteration_does_not_fail_on_untracked_without_diff(self) -> None:
        proposal = AgentFixIterationRecord(
            status="done",
            reasoning_summary="added a new helper",
            confidence=0.8,
            changed_files=["src/new_helper.py"],
        )
        changes = WorkspaceChangeSet(
            modified_files=[],
            added_files=["src/new_helper.py"],
            deleted_files=[],
            untracked_files=["src/new_helper.py"],
            diff="",
            diff_complete=False,
        )
        validation = validate_iteration(
            proposal=proposal,
            changes=changes,
            current_test_execution=TestExecution(exit_code=1, timed_out=False, output="fail", signature="sig-now"),
            baseline_test_execution=None,
        )
        self.assertTrue(validation.ok)

    def test_output_builder_copies_mutable_state(self) -> None:
        state = RunState(
            accumulated_logs=["log-1"],
            latest_artifacts={"a": 1},
        )
        builder = RunOutputBuilder()
        identity = build_run_identity(
            run_input=RunInput(prompt="Fix it"),
            agent_config={"arch": "mono"},
            iteration=1,
            run_id="run-123",
        )

        output = builder.build(
            identity=identity,
            status=RunStatus.PARTIAL,
            stop_reason=StopReason.NO_PROGRESS,
            state=state,
            cfg=object(),
        )

        output.logs.append("mutated")
        output.artifacts["b"] = 2

        self.assertEqual(state.accumulated_logs, ["log-1"])
        self.assertEqual(state.latest_artifacts, {"a": 1})

    def test_error_classification(self) -> None:
        self.assertEqual(error_category_from_exception(ProviderExecutionError("x")), ErrorCategory.MODEL)
        self.assertEqual(error_category_from_exception(WorkspaceError("x")), ErrorCategory.INFRA)
        self.assertEqual(error_category_from_exception(RuntimeError("x")), ErrorCategory.UNKNOWN)


if __name__ == "__main__":
    unittest.main()
