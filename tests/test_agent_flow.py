from __future__ import annotations

import json
import unittest
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from agents.mcp import MCPServer
from pydantic import SecretStr

from llm_autofix_agents.agent_flow import run_agent_baseline
from llm_autofix_agents.contracts import ErrorCategory, RunInput, RunStatus, StopReason
from llm_autofix_agents.flow import persist_iteration_artifacts as _persist_iteration_artifacts
from llm_autofix_agents.flow.git_ops import TempBranchContext
from llm_autofix_agents.llm.provider import AgentFixProposal
from llm_autofix_agents.llm.settings import LLMSettings, ProviderType


class AgentFlowTests(unittest.TestCase):
    def setUp(self) -> None:
        self._persist_patcher = patch(
            "llm_autofix_agents.agent_flow._persist_iteration_artifacts",
            return_value={},
        )
        self._git_repo_patcher = patch(
            "llm_autofix_agents.agent_flow._is_git_repository",
            return_value=False,
        )
        self._persist_patcher.start()
        self._git_repo_patcher.start()

    def tearDown(self) -> None:
        self._persist_patcher.stop()
        self._git_repo_patcher.stop()

    def test_run_agent_baseline_success(self) -> None:
        provider = _CapturingProvider(_proposal(rationale="suggested fix"))
        with patch(
            "llm_autofix_agents.agent_flow._collect_repo_diff",
            return_value="",
        ):
            output = run_agent_baseline(
                RunInput(prompt="Fix parser failure"),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.SUCCESS)
        self.assertEqual(output.stop_reason, StopReason.COMPLETED)
        self.assertIn("rationale: suggested fix", output.final_message or "")
        self.assertEqual(output.identity.iteration, 1)
        self.assertIn("stage=agent", output.logs)
        self.assertIn("toolset=mcp-stdio", output.logs)
        self.assertIsNotNone(provider.last_user_input)
        assert provider.last_user_input is not None
        self.assertEqual(provider.last_user_input, "Fix parser failure")
        self.assertIsNotNone(provider.last_mcp_servers)
        assert provider.last_mcp_servers is not None
        self.assertEqual(len(provider.last_mcp_servers), 3)
        self.assertEqual([server.name for server in provider.last_mcp_servers], ["filesystem", "shell", "web-search"])

    def test_run_agent_baseline_stops_on_no_progress(self) -> None:
        provider = _SequencedProvider([_proposal(rationale="same fix"), _proposal(rationale="same fix")])
        with patch(
            "llm_autofix_agents.agent_flow._run_test_command",
            side_effect=[
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-baseline"),
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._snapshot_repo_state",
            return_value={"src/a.py": "abc"},
        ), patch(
            "llm_autofix_agents.agent_flow._collect_repo_diff",
            return_value="",
        ):
            output = run_agent_baseline(
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
                _proposal(rationale="attempt one", patch="--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b1"),
                _proposal(rationale="attempt two", patch="--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b2"),
                _proposal(rationale="attempt three", patch="--- a/a.py\n+++ b/a.py\n@@ -1 +1 @@\n-a\n+b3"),
            ]
        )
        with patch(
            "llm_autofix_agents.agent_flow._run_test_command",
            side_effect=[
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-baseline"),
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._snapshot_repo_state",
            side_effect=[
                {"src/a.py": "v1"},
                {"src/a.py": "v2"},
                {"src/a.py": "v2"},
                {"src/a.py": "v3"},
                {"src/a.py": "v3"},
                {"src/a.py": "v4"},
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._collect_repo_diff",
            return_value="diff --git a/src/a.py b/src/a.py",
        ):
            output = run_agent_baseline(
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

    def test_run_agent_baseline_stops_on_changed_files_mismatch(self) -> None:
        provider = _SequencedProvider(
            [
                _proposal(
                    rationale="attempt one",
                    changed_files=["src/other.py"],
                )
            ]
        )
        with patch(
            "llm_autofix_agents.agent_flow._run_test_command",
            side_effect=[
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-baseline"),
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._snapshot_repo_state",
            side_effect=[
                {"src/a.py": "v1"},
                {"src/a.py": "v2"},
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._collect_repo_diff",
            return_value="diff --git a/src/a.py b/src/a.py",
        ):
            output = run_agent_baseline(
                RunInput(
                    prompt="Fix parser failure",
                    test_command="uv run python -m unittest",
                ),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.FAILED)
        self.assertEqual(output.stop_reason, StopReason.VALIDATION_FAILURE)
        self.assertEqual(output.errors[0].category, ErrorCategory.VALIDATION)
        self.assertIn("proposal_changed_files", output.errors[0].details)

    def test_run_agent_baseline_persists_artifacts_in_results(self) -> None:
        provider = _SequencedProvider([_proposal(rationale="fix tests", changed_files=["src/a.py"])])
        self._persist_patcher.stop()

        try:
            with TemporaryDirectory() as tmp_dir:
                repo_root = Path(tmp_dir)
                with patch(
                    "llm_autofix_agents.agent_flow._persist_iteration_artifacts",
                    side_effect=_persist_iteration_artifacts,
                ), patch(
                    "llm_autofix_agents.agent_flow._run_test_command",
                    side_effect=[
                        SimpleNamespace(
                            exit_code=1,
                            timed_out=False,
                            output="FAILED (failures=1)",
                            signature="sig-baseline",
                        ),
                        SimpleNamespace(exit_code=0, timed_out=False, output="OK", signature="sig-ok"),
                    ],
                ), patch(
                    "llm_autofix_agents.agent_flow._snapshot_repo_state",
                    side_effect=[
                        {"src/a.py": "v1"},
                        {"src/a.py": "v2"},
                    ],
                ), patch(
                    "llm_autofix_agents.agent_flow._collect_repo_diff",
                    return_value="diff --git a/src/a.py b/src/a.py",
                ):
                    output = run_agent_baseline(
                        RunInput(
                            prompt="Fix parser failure",
                            test_command="uv run python -m unittest",
                            target_repo=str(repo_root),
                        ),
                        settings=_settings(),
                        provider=provider,
                    )

                self.assertEqual(output.status, RunStatus.SUCCESS)
                self.assertIn("directory", output.artifacts)
                diff_file = repo_root / output.artifacts["diff_file"]
                metadata_file = repo_root / output.artifacts["metadata_file"]
                manifest_file = repo_root / output.artifacts["manifest_file"]
                self.assertTrue(diff_file.exists())
                self.assertTrue(metadata_file.exists())
                self.assertTrue(manifest_file.exists())
                manifest_payload = json.loads(manifest_file.read_text(encoding="utf-8"))
                self.assertEqual(manifest_payload["run_id"], output.identity.run_id)
                self.assertEqual(manifest_payload["iterations_count"], 1)
                self.assertEqual(manifest_payload["iterations"][0]["iteration"], 1)
        finally:
            self._persist_patcher.start()

    def test_run_agent_baseline_maps_provider_error(self) -> None:
        output = run_agent_baseline(
            RunInput(prompt="Fix parser failure"),
            settings=_settings(),
            provider=_FailingProvider(),
        )

        self.assertEqual(output.status, RunStatus.FAILED)
        self.assertEqual(output.stop_reason, StopReason.INFRA_FAILURE)
        self.assertEqual(len(output.errors), 1)
        self.assertEqual(output.errors[0].category, ErrorCategory.MODEL)

    def test_run_agent_baseline_stops_on_regression_detected(self) -> None:
        provider = _SequencedProvider([_proposal(rationale="introduce breaking change")])
        with patch(
            "llm_autofix_agents.agent_flow._run_test_command",
            side_effect=[
                SimpleNamespace(exit_code=0, timed_out=False, output="OK", signature="sig-baseline-ok"),
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-now-fail"),
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._snapshot_repo_state",
            side_effect=[
                {"src/a.py": "v1"},
                {"src/a.py": "v2"},
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._collect_repo_diff",
            return_value="diff --git a/src/a.py b/src/a.py",
        ):
            output = run_agent_baseline(
                RunInput(
                    prompt="Fix parser failure",
                    test_command="uv run python -m unittest",
                ),
                settings=_settings(),
                provider=provider,
            )

        self.assertEqual(output.status, RunStatus.FAILED)
        self.assertEqual(output.stop_reason, StopReason.VALIDATION_FAILURE)
        self.assertEqual(len(output.errors), 1)
        self.assertEqual(output.errors[0].category, ErrorCategory.VALIDATION)
        self.assertIn("validation_result=regression_detected", output.logs)

    def test_run_agent_baseline_no_regression_when_baseline_failing(self) -> None:
        provider = _SequencedProvider([_proposal(rationale="fix tests")])
        with patch(
            "llm_autofix_agents.agent_flow._run_test_command",
            side_effect=[
                SimpleNamespace(
                    exit_code=1,
                    timed_out=False,
                    output="FAILED (failures=1)",
                    signature="sig-baseline-fail",
                ),
                SimpleNamespace(exit_code=0, timed_out=False, output="OK", signature="sig-now-ok"),
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._snapshot_repo_state",
            side_effect=[
                {"src/a.py": "v1"},
                {"src/a.py": "v2"},
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._collect_repo_diff",
            return_value="diff --git a/src/a.py b/src/a.py",
        ):
            output = run_agent_baseline(
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
        provider = _CapturingProvider(_proposal(rationale="suggested fix"))
        self._git_repo_patcher.stop()
        with patch(
            "llm_autofix_agents.agent_flow._is_git_repository",
            return_value=True,
        ), patch(
            "llm_autofix_agents.agent_flow._create_temp_branch",
            return_value=TempBranchContext(
                branch_name="autofix/20260418T100000Z-run-abc",
                original_branch="main",
            ),
        ) as create_branch, patch(
            "llm_autofix_agents.agent_flow._restore_original_branch",
        ) as restore_branch, patch(
            "llm_autofix_agents.agent_flow._delete_branch",
        ) as delete_branch, patch(
            "llm_autofix_agents.agent_flow._collect_repo_diff",
            return_value="",
        ):
            output = run_agent_baseline(
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
        provider = _SequencedProvider(
            [
                _proposal(
                    rationale="attempt one",
                    changed_files=["src/other.py"],
                )
            ]
        )
        self._git_repo_patcher.stop()
        with patch(
            "llm_autofix_agents.agent_flow._is_git_repository",
            return_value=True,
        ), patch(
            "llm_autofix_agents.agent_flow._create_temp_branch",
            return_value=TempBranchContext(
                branch_name="autofix/20260418T100000Z-run-abc",
                original_branch="main",
            ),
        ), patch(
            "llm_autofix_agents.agent_flow._restore_original_branch",
        ) as restore_branch, patch(
            "llm_autofix_agents.agent_flow._delete_branch",
        ) as delete_branch, patch(
            "llm_autofix_agents.agent_flow._run_test_command",
            side_effect=[
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-baseline"),
                SimpleNamespace(exit_code=1, timed_out=False, output="FAILED (failures=1)", signature="sig-1"),
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._snapshot_repo_state",
            side_effect=[
                {"src/a.py": "v1"},
                {"src/a.py": "v2"},
            ],
        ), patch(
            "llm_autofix_agents.agent_flow._collect_repo_diff",
            return_value="diff --git a/src/a.py b/src/a.py",
        ):
            output = run_agent_baseline(
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
        provider = _CapturingProvider(_proposal(rationale="suggested fix"))
        self._git_repo_patcher.stop()
        with patch(
            "llm_autofix_agents.agent_flow._is_git_repository",
            return_value=True,
        ), patch(
            "llm_autofix_agents.agent_flow._create_temp_branch",
            return_value=TempBranchContext(
                branch_name="autofix/20260418T100000Z-run-abc",
                original_branch="main",
            ),
        ), patch(
            "llm_autofix_agents.agent_flow._restore_original_branch",
            side_effect=RuntimeError("cannot switch back"),
        ), patch(
            "llm_autofix_agents.agent_flow._delete_branch",
        ), patch(
            "llm_autofix_agents.agent_flow._collect_repo_diff",
            return_value="",
        ):
            output = run_agent_baseline(
                RunInput(prompt="Fix parser failure"),
                settings=_settings(),
                provider=provider,
            )

        self._git_repo_patcher.start()
        self.assertEqual(output.status, RunStatus.FAILED)
        self.assertEqual(output.stop_reason, StopReason.INFRA_FAILURE)
        self.assertEqual(len(output.errors), 1)
        self.assertEqual(output.errors[0].category, ErrorCategory.INFRA)
        self.assertIn("branch_cleanup_error", output.errors[0].details)


class _CapturingProvider:
    def __init__(self, response: AgentFixProposal) -> None:
        self._response = response
        self.last_user_input: str | None = None
        self.last_mcp_servers: list[MCPServer] | None = None

    async def run_prompt(
        self,
        *,
        instructions: str,
        user_input: str,
        max_turns: int,
        tools: Sequence[object] | None = None,
        mcp_servers: Sequence[MCPServer] | None = None,
    ) -> AgentFixProposal:
        del instructions, max_turns
        self.last_user_input = user_input
        del tools
        self.last_mcp_servers = list(mcp_servers) if mcp_servers is not None else None
        return self._response


class _FailingProvider:
    async def run_prompt(
        self,
        *,
        instructions: str,
        user_input: str,
        max_turns: int,
        tools: Sequence[object] | None = None,
        mcp_servers: Sequence[MCPServer] | None = None,
    ) -> AgentFixProposal:
        del instructions, user_input, max_turns, tools, mcp_servers
        raise RuntimeError("provider down")


class _SequencedProvider:
    def __init__(self, responses: list[AgentFixProposal]) -> None:
        self._responses = responses
        self._calls = 0

    async def run_prompt(
        self,
        *,
        instructions: str,
        user_input: str,
        max_turns: int,
        tools: Sequence[object] | None = None,
        mcp_servers: Sequence[MCPServer] | None = None,
    ) -> AgentFixProposal:
        del instructions, user_input, max_turns, tools, mcp_servers
        if self._calls >= len(self._responses):
            raise RuntimeError("no more responses configured")
        response = self._responses[self._calls]
        self._calls += 1
        return response


def _proposal(
    *,
    rationale: str,
    patch: str | None = None,
    confidence: float = 0.8,
    changed_files: list[str] | None = None,
) -> AgentFixProposal:
    return AgentFixProposal(
        patch_unified_diff=patch,
        rationale=rationale,
        confidence=confidence,
        changed_files=changed_files if changed_files is not None else ["src/a.py"],
    )


def _settings() -> LLMSettings:
    return LLMSettings(
        provider=ProviderType.GEMINI,
        model="gemini-2.5-flash",
        api_key=SecretStr("gemini-key"),
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        max_turns=3,
        tracing_disabled=True,
    )


if __name__ == "__main__":
    unittest.main()
