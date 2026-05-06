from __future__ import annotations

import unittest

from pydantic import ValidationError

from llm_autofix_agents.contracts import (
    ContainerInstantiation,
    RunInput,
    TestResults,
    ToolCallTrace,
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

    def test_container_instantiation_from_env_is_loaded(self) -> None:
        instantiation = ContainerInstantiation.from_env(
            {
                "RUN_REPOSITORY": "quixbugs",
                "RUN_BRANCH": "main",
                "RUN_ARCHITECTURE": "mono_agent",
                "RUN_AGENT_MODELS": '{"main":"llama3.1:8b"}',
            }
        )
        self.assertEqual(instantiation.repository, "quixbugs")
        self.assertEqual(instantiation.branch, "main")
        self.assertEqual(instantiation.architecture, "mono_agent")
        self.assertEqual(instantiation.agent_models, {"main": "llama3.1:8b"})
        self.assertIsNone(instantiation.bootstrap_prompt)

    def test_container_instantiation_with_optional_prompt(self) -> None:
        instantiation = ContainerInstantiation.from_env(
            {
                "RUN_REPOSITORY": "quixbugs",
                "RUN_BRANCH": "main",
                "RUN_ARCHITECTURE": "mono_agent",
                "RUN_AGENT_MODELS": '{"main":"llama3.1:8b"}',
                "RUN_BOOTSTRAP_PROMPT": "Fix failing tests with minimal changes.",
            }
        )
        self.assertEqual(instantiation.bootstrap_prompt, "Fix failing tests with minimal changes.")

    def test_container_instantiation_rejects_invalid_models_json(self) -> None:
        with self.assertRaisesRegex(ValueError, "RUN_AGENT_MODELS must be valid JSON"):
            ContainerInstantiation.from_env(
                {
                    "RUN_REPOSITORY": "quixbugs",
                    "RUN_BRANCH": "main",
                    "RUN_ARCHITECTURE": "mono_agent",
                    "RUN_AGENT_MODELS": "not-json",
                }
            )

    def test_container_instantiation_rejects_invalid_architecture(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unsupported RUN_ARCHITECTURE"):
            ContainerInstantiation.from_env(
                {
                    "RUN_REPOSITORY": "quixbugs",
                    "RUN_BRANCH": "main",
                    "RUN_ARCHITECTURE": "mono-agent",
                    "RUN_AGENT_MODELS": '{"main":"llama3.1:8b"}',
                }
            )

    def test_tool_call_trace_normalizes_status(self) -> None:
        trace = ToolCallTrace(
            iteration=1,
            name=" shell ",
            status=" ok ",
        )
        self.assertEqual(trace.name, "shell")
        self.assertEqual(trace.status, "ok")


if __name__ == "__main__":
    unittest.main()
