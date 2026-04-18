from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import Any

from llm_autofix_agents.contracts import (
    ErrorCategory,
    RunError,
    RunInput,
    RunOutput,
    RunStatus,
    StopReason,
    TestResults,
    build_run_identity,
)
from llm_autofix_agents.flow_support import (
    TestExecution,
)
from llm_autofix_agents.flow_support import (
    build_iteration_input as _build_iteration_input,
)
from llm_autofix_agents.flow_support import (
    can_complete_early as _can_complete_early,
)
from llm_autofix_agents.flow_support import (
    collect_repo_diff as _collect_repo_diff,
)
from llm_autofix_agents.flow_support import (
    detect_changed_files as _detect_changed_files,
)
from llm_autofix_agents.flow_support import (
    is_no_progress as _is_no_progress,
)
from llm_autofix_agents.flow_support import (
    resolve_repo_root as _resolve_repo_root,
)
from llm_autofix_agents.flow_support import (
    resolve_test_timeout_seconds as _resolve_test_timeout_seconds,
)
from llm_autofix_agents.flow_support import (
    run_test_command as _run_test_command,
)
from llm_autofix_agents.flow_support import (
    snapshot_repo_state as _snapshot_repo_state,
)
from llm_autofix_agents.flow_support import (
    to_test_results as _to_test_results,
)
from llm_autofix_agents.llm.provider import AgentFixProposal, LLMProvider, create_provider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.toolset import build_mcp_servers

_BASELINE_INSTRUCTIONS = (
    "You are an APR baseline agent operating autonomously. "
    "Decide the flow using available MCP tools, avoid hardcoded assumptions, "
    "run commands through the shell MCP when validation is needed, "
    "apply and validate changes directly in the target repository via MCP tools, "
    "and then return a structured execution report with: "
    "patch_unified_diff, rationale, confidence, changed_files, notes."
)

_TestExecution = TestExecution


def run_agent_baseline(
    run_input: RunInput,
    *,
    settings: LLMSettings | None = None,
    provider: LLMProvider | None = None,
) -> RunOutput:
    resolved_settings = settings if settings is not None else LLMSettings.from_env()
    resolved_provider = provider if provider is not None else create_provider(resolved_settings)
    max_iterations = _resolve_max_iterations(run_input.metadata)

    run_id: str | None = None
    previous_proposal_signature: str | None = None
    previous_test_signature: str | None = None
    accumulated_logs: list[str] = []
    mcp_server_count = 0
    latest_tests: TestResults | None = None
    latest_diff = ""
    test_timeout_seconds = _resolve_test_timeout_seconds(run_input.metadata)
    repo_root = _resolve_repo_root(run_input.target_repo)

    try:
        mcp_servers = build_mcp_servers(target_repo=run_input.target_repo)
        mcp_server_count = len(mcp_servers)

        final_message: str | None = None
        for iteration in range(1, max_iterations + 1):
            identity = build_run_identity(
                run_input=run_input,
                agent_config=resolved_settings.fingerprint_payload(),
                iteration=iteration,
                run_id=run_id,
            )
            run_id = identity.run_id
            before_snapshot = _snapshot_repo_state(repo_root) if run_input.test_command is not None else {}

            proposal = _run_sync(
                resolved_provider.run_prompt(
                    instructions=_BASELINE_INSTRUCTIONS,
                    user_input=_build_iteration_input(
                        prompt=run_input.prompt,
                        iteration=iteration,
                        max_iterations=max_iterations,
                        previous_message=final_message,
                    ),
                    max_turns=resolved_settings.max_turns,
                    mcp_servers=mcp_servers,
                )
            )
            final_message = _render_final_message(proposal)
            latest_diff = _collect_repo_diff(repo_root)

            after_snapshot = _snapshot_repo_state(repo_root) if run_input.test_command is not None else {}
            changed_files = _detect_changed_files(before_snapshot, after_snapshot)
            repo_changed = len(changed_files) > 0
            test_execution = _run_test_command(
                run_input.test_command,
                cwd=repo_root,
                timeout_seconds=test_timeout_seconds,
            )
            latest_tests = _to_test_results(test_execution)

            accumulated_logs.extend(
                _build_run_logs(
                    provider=resolved_settings.provider.value,
                    model=resolved_settings.model,
                    result="ok",
                    mcp_server_count=mcp_server_count,
                    iteration=iteration,
                    max_iterations=max_iterations,
                    changed_files=changed_files,
                    test_execution=test_execution,
                    repo_changed=repo_changed,
                    confidence=proposal.confidence,
                )
            )

            if _is_no_progress(
                previous_message=previous_proposal_signature,
                current_message=_proposal_signature(proposal),
                previous_test_signature=previous_test_signature,
                current_test_signature=test_execution.signature,
                changed_files=changed_files,
            ):
                return RunOutput(
                    identity=identity,
                    status=RunStatus.PARTIAL,
                    stop_reason=StopReason.NO_PROGRESS,
                    diff=latest_diff,
                    logs=accumulated_logs,
                    tests=latest_tests,
                    final_message=final_message,
                )

            previous_proposal_signature = _proposal_signature(proposal)
            previous_test_signature = test_execution.signature

            if _can_complete_early(run_input=run_input, test_execution=test_execution):
                return RunOutput(
                    identity=identity,
                    status=RunStatus.SUCCESS,
                    stop_reason=StopReason.COMPLETED,
                    diff=latest_diff,
                    logs=accumulated_logs,
                    tests=latest_tests,
                    final_message=final_message,
                )

        assert final_message is not None
        identity = build_run_identity(
            run_input=run_input,
            agent_config=resolved_settings.fingerprint_payload(),
            iteration=max_iterations,
            run_id=run_id,
        )
        return RunOutput(
            identity=identity,
            status=RunStatus.PARTIAL,
            stop_reason=StopReason.MAX_ITERATIONS,
            diff=latest_diff,
            logs=accumulated_logs,
            tests=latest_tests,
            final_message=final_message,
        )
    except Exception as exc:
        failure_identity = build_run_identity(
            run_input=run_input,
            agent_config=resolved_settings.fingerprint_payload(),
            iteration=1,
            run_id=run_id,
        )
        return RunOutput(
            identity=failure_identity,
            status=RunStatus.FAILED,
            stop_reason=StopReason.INFRA_FAILURE,
            logs=accumulated_logs
            + _build_run_logs(
                provider=resolved_settings.provider.value,
                model=resolved_settings.model,
                result="error",
                mcp_server_count=mcp_server_count,
                iteration=1,
                max_iterations=max_iterations,
                changed_files=[],
                test_execution=None,
                repo_changed=False,
                confidence=0.0,
            ),
            errors=[
                RunError(
                    category=ErrorCategory.MODEL,
                    message=str(exc),
                    retryable=False,
                    details={"provider": resolved_settings.provider.value},
                )
            ],
            final_message=None,
        )


def _run_sync(awaitable: Coroutine[object, object, AgentFixProposal]) -> AgentFixProposal:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("run_agent_baseline cannot be called from an active event loop")


def _build_run_logs(
    *,
    provider: str,
    model: str,
    result: str,
    mcp_server_count: int,
    iteration: int,
    max_iterations: int,
    changed_files: list[str],
    test_execution: _TestExecution | None,
    repo_changed: bool,
    confidence: float,
) -> list[str]:
    lines = [
        "stage=agent",
        "toolset=mcp-stdio",
        f"mcp_servers={mcp_server_count}",
        f"provider={provider}",
        f"model={model}",
        f"iteration={iteration}/{max_iterations}",
        f"changed_files={len(changed_files)}",
        f"repo_changed={repo_changed}",
        f"proposal_confidence={confidence:.3f}",
        f"result={result}",
    ]
    if test_execution is not None:
        lines.extend(
            [
                f"test_exit_code={test_execution.exit_code}",
                f"test_timed_out={test_execution.timed_out}",
                f"test_signature={test_execution.signature}",
            ]
        )
    return lines


def _resolve_max_iterations(metadata: dict[str, Any]) -> int:
    value = metadata.get("max_iterations")
    if value is None:
        return 3
    if not isinstance(value, int):
        raise ValueError("metadata.max_iterations must be an integer")
    if value < 1 or value > 3:
        raise ValueError("metadata.max_iterations must be between 1 and 3")
    return value


def _proposal_signature(proposal: AgentFixProposal) -> str:
    rationale = " ".join(proposal.rationale.split()).strip().lower()
    changed = "|".join(proposal.changed_files)
    notes = " ".join((proposal.notes or "").split()).strip().lower()
    return f"rationale={rationale}|changed={changed}|notes={notes}"


def _render_final_message(proposal: AgentFixProposal) -> str:
    return (
        f"rationale: {proposal.rationale}\n"
        f"confidence: {proposal.confidence:.3f}\n"
        f"changed_files: {', '.join(proposal.changed_files) if proposal.changed_files else '(unspecified)'}"
    )
