from __future__ import annotations

import unittest

from pydantic import ValidationError

from llm_autofix_agents.contracts import (
    RunInput,
    TestResults,
    build_run_identity,
    compute_run_fingerprint,
)


class ContractsTests(unittest.TestCase):
    def test_prompt_is_normalized(self) -> None:
        run_input = RunInput(prompt="  fix parser failure  ")
        self.assertEqual(run_input.prompt, "fix parser failure")

    def test_test_results_reject_inconsistent_counts(self) -> None:
        with self.assertRaises(ValidationError):
            TestResults(total=1, passed=1, failed=1)

    def test_fingerprint_is_deterministic(self) -> None:
        run_input = RunInput(prompt="stabilize test")
        fingerprint_a = compute_run_fingerprint(run_input, {"model": "baseline", "max_iterations": 3})
        fingerprint_b = compute_run_fingerprint(run_input, {"max_iterations": 3, "model": "baseline"})
        self.assertEqual(fingerprint_a, fingerprint_b)

    def test_build_run_identity_uses_given_run_id(self) -> None:
        run_input = RunInput(prompt="repair flaky test")
        identity = build_run_identity(
            run_input=run_input,
            agent_config={"model": "baseline"},
            iteration=2,
            run_id="run-fixed-id",
        )
        self.assertEqual(identity.run_id, "run-fixed-id")
        self.assertEqual(identity.iteration, 2)
        self.assertEqual(identity.iteration_id, "run-fixed-id-it02")


if __name__ == "__main__":
    unittest.main()
