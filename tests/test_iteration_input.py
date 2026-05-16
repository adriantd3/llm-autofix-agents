from __future__ import annotations

import unittest

from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet
from llm_autofix_agents.flow.policies.iteration import build_continuation_snapshot, build_iteration_input
from llm_autofix_agents.llm.provider import AgentFixIterationRecord, AgentFixIterationResult


class IterationInputTests(unittest.TestCase):
    def test_first_iteration_uses_failing_test_output(self) -> None:
        user_input = build_iteration_input(
            prompt="legacy prompt should not be primary",
            iteration=1,
            max_iterations=3,
            previous_message=None,
            latest_snapshot=None,
            baseline_test_execution=TestExecution(
                exit_code=1,
                timed_out=False,
                output="FAILED test_gcd.py::test_gcd_case",
                signature="sig-123",
            ),
            test_command="uv run --with pytest pytest python_testcases/test_gcd.py",
        )

        self.assertIn("autonomous software repair agent", user_input)
        self.assertIn("FAILED test_gcd.py::test_gcd_case", user_input)
        self.assertIn("python_testcases/test_gcd.py", user_input)
        self.assertIn("Compact test output:", user_input)
        self.assertNotIn("legacy prompt should not be primary", user_input)

    def test_first_iteration_includes_critical_rules(self) -> None:
        user_input = build_iteration_input(
            prompt="prompt",
            iteration=1,
            max_iterations=3,
            previous_message=None,
            latest_snapshot=None,
            baseline_test_execution=TestExecution(
                exit_code=1,
                timed_out=False,
                output="FAILED",
                signature="sig",
            ),
            test_command="pytest",
        )

        self.assertIn("NEVER modify test files", user_input)
        self.assertIn("Do NOT re-run the failing test before making code changes", user_input)

    def test_first_iteration_falls_back_to_prompt_without_baseline_failure(self) -> None:
        user_input = build_iteration_input(
            prompt="fallback prompt",
            iteration=1,
            max_iterations=3,
            previous_message=None,
            latest_snapshot=None,
            baseline_test_execution=None,
            test_command=None,
        )

        self.assertEqual(user_input, "fallback prompt")

    def test_followup_iteration_includes_previous_summary_and_snapshot(self) -> None:
        snapshot = build_continuation_snapshot(
            proposal=AgentFixIterationRecord(
                proposal=AgentFixIterationResult(
                    status="in_progress",
                    reasoning_summary="summary",
                    confidence=0.5,
                    notes="Checked gcd.py, updated loop",
                ),
            ),
            changes=WorkspaceChangeSet(
                modified_files=["gcd.py"],
                added_files=[],
                deleted_files=[],
                untracked_files=[],
                diff="",
                diff_excludes_untracked=False,
            ),
            test_execution=TestExecution(
                exit_code=1,
                timed_out=False,
                output="FAILED",
                signature="sig-last",
            ),
        )
        user_input = build_iteration_input(
            prompt="fallback prompt",
            iteration=2,
            max_iterations=3,
            previous_message="patched gcd but tests still fail",
            latest_snapshot=snapshot,
            baseline_test_execution=None,
            test_command=None,
        )

        self.assertIn("[ITERATION 2/3]", user_input)
        self.assertIn("patched gcd but tests still fail", user_input)
        self.assertIn("Observed continuation snapshot", user_input)
        self.assertIn("Changed files observed", user_input)
        self.assertIn("gcd.py", user_input)
        self.assertNotIn("Initial failing test context", user_input)

    def test_followup_iteration_with_validation_feedback(self) -> None:
        user_input = build_iteration_input(
            prompt="fallback prompt",
            iteration=2,
            max_iterations=3,
            previous_message="attempted fix",
            latest_snapshot="Observed continuation snapshot (runtime evidence):\n- Changed files observed:\n  - gcd.py",
            baseline_test_execution=None,
            test_command=None,
            validation_feedback="You modified test files (test_foo.py). DO NOT modify test files.",
        )

        self.assertIn("[ITERATION 2/3]", user_input)
        self.assertIn("VALIDATION REJECTION FROM PREVIOUS ITERATION", user_input)
        self.assertIn("You modified test files (test_foo.py)", user_input)
        self.assertIn("DO NOT repeat the same mistake", user_input)

    def test_first_iteration_with_validation_feedback(self) -> None:
        user_input = build_iteration_input(
            prompt="prompt without baseline",
            iteration=1,
            max_iterations=3,
            previous_message=None,
            latest_snapshot=None,
            baseline_test_execution=None,
            test_command=None,
            validation_feedback="You modified test files. Fix ONLY source code.",
        )

        self.assertIn("VALIDATION REJECTION FROM PREVIOUS ITERATION", user_input)
        self.assertIn("Fix ONLY source code", user_input)
        self.assertIn("prompt without baseline", user_input)

    def test_first_iteration_failing_test_with_validation_feedback(self) -> None:
        user_input = build_iteration_input(
            prompt="prompt",
            iteration=1,
            max_iterations=3,
            previous_message=None,
            latest_snapshot=None,
            baseline_test_execution=TestExecution(
                exit_code=1,
                timed_out=False,
                output="FAILED",
                signature="sig",
            ),
            test_command="pytest",
            validation_feedback="REJECTED: test files modified",
        )

        self.assertIn("VALIDATION REJECTION FROM PREVIOUS ITERATION", user_input)
        self.assertIn("REJECTED: test files modified", user_input)
        self.assertIn("autonomous software repair agent", user_input)

    def test_no_validation_feedback_by_default(self) -> None:
        user_input = build_iteration_input(
            prompt="prompt",
            iteration=2,
            max_iterations=3,
            previous_message="previous",
            latest_snapshot=None,
            baseline_test_execution=None,
            test_command=None,
        )

        self.assertNotIn("VALIDATION REJECTION", user_input)

    def test_no_edit_previous_iteration_shows_assertive_task(self) -> None:
        snapshot_with_warning = (
            "Observed continuation snapshot (runtime evidence):\n"
            "- Changed files observed:\n"
            "  - (none)\n"
            "⚠ WARNING: No source files were modified in the previous iteration. "
            "You MUST apply at least one code change before calling run_tests."
        )
        user_input = build_iteration_input(
            prompt="fallback prompt",
            iteration=2,
            max_iterations=3,
            previous_message="ran out of turns",
            latest_snapshot=snapshot_with_warning,
            baseline_test_execution=None,
            test_command=None,
        )

        self.assertIn("You MUST apply a code change this iteration", user_input)
        self.assertNotIn("Continue improving the repair strategy", user_input)

    def test_edit_made_previous_iteration_shows_normal_task(self) -> None:
        snapshot_without_warning = (
            "Observed continuation snapshot (runtime evidence):\n"
            "- Changed files observed:\n"
            "  - src/foo.py\n"
        )
        user_input = build_iteration_input(
            prompt="fallback prompt",
            iteration=2,
            max_iterations=3,
            previous_message="applied fix but tests still fail",
            latest_snapshot=snapshot_without_warning,
            baseline_test_execution=None,
            test_command=None,
        )

        self.assertIn("Continue improving the repair strategy", user_input)
        self.assertNotIn("You MUST apply a code change this iteration", user_input)


if __name__ == "__main__":
    unittest.main()
