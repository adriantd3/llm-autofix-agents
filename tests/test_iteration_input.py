from __future__ import annotations

import unittest

from llm_autofix_agents.flow.models import TestExecution
from llm_autofix_agents.flow.policies.iteration import build_iteration_input


class IterationInputTests(unittest.TestCase):
    def test_first_iteration_uses_failing_test_output(self) -> None:
        user_input = build_iteration_input(
            prompt="legacy prompt should not be primary",
            iteration=1,
            max_iterations=3,
            previous_message=None,
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
        self.assertNotIn("legacy prompt should not be primary", user_input)

    def test_first_iteration_falls_back_to_prompt_without_baseline_failure(self) -> None:
        user_input = build_iteration_input(
            prompt="fallback prompt",
            iteration=1,
            max_iterations=3,
            previous_message=None,
            baseline_test_execution=None,
            test_command=None,
        )

        self.assertEqual(user_input, "fallback prompt")

    def test_followup_iteration_includes_previous_summary_and_baseline_hint(self) -> None:
        user_input = build_iteration_input(
            prompt="fallback prompt",
            iteration=2,
            max_iterations=3,
            previous_message="patched gcd but tests still fail",
            baseline_test_execution=TestExecution(
                exit_code=1,
                timed_out=False,
                output="FAILED",
                signature="sig-base",
            ),
            test_command="uv run --with pytest pytest python_testcases/test_gcd.py",
        )

        self.assertIn("[ITERATION 2/3]", user_input)
        self.assertIn("patched gcd but tests still fail", user_input)
        self.assertIn("signature=sig-base", user_input)


if __name__ == "__main__":
    unittest.main()
