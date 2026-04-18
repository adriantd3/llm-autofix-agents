from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from pathlib import Path
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
from llm_autofix_agents.flow import TestExecution
from llm_autofix_agents.flow import (
    build_iteration_input as _build_iteration_input,
)
from llm_autofix_agents.flow import (
    can_complete_early as _can_complete_early,
)
from llm_autofix_agents.flow import (
    collect_repo_diff as _collect_repo_diff,
)
from llm_autofix_agents.flow import (
    create_temp_branch as _create_temp_branch,
)
from llm_autofix_agents.flow import (
    delete_branch as _delete_branch,
)
from llm_autofix_agents.flow import (
    detect_changed_files as _detect_changed_files,
)
from llm_autofix_agents.flow import (
    is_git_repository as _is_git_repository,
)
from llm_autofix_agents.flow import (
    is_no_progress as _is_no_progress,
)
from llm_autofix_agents.flow import (
    is_regression as _is_regression,
)
from llm_autofix_agents.flow import (
    load_ignore_rules as _load_ignore_rules,
)
from llm_autofix_agents.flow import (
    persist_iteration_artifacts as _persist_iteration_artifacts,
)
from llm_autofix_agents.flow import (
    resolve_repo_root as _resolve_repo_root,
)
from llm_autofix_agents.flow import (
    resolve_test_timeout_seconds as _resolve_test_timeout_seconds,
)
from llm_autofix_agents.flow import (
    restore_original_branch as _restore_original_branch,
)
from llm_autofix_agents.flow import (
    run_test_command as _run_test_command,
)
from llm_autofix_agents.flow import (
    snapshot_repo_state as _snapshot_repo_state,
)
from llm_autofix_agents.flow import (
    to_test_results as _to_test_results,
)
from llm_autofix_agents.flow import (
    validate_changed_files_coherence as _validate_changed_files_coherence,
)
from llm_autofix_agents.flow import (
    validate_diff_integrity as _validate_diff_integrity,
)
from llm_autofix_agents.flow.git_ops import TempBranchContext
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
    latest_artifacts: dict[str, Any] = {}
    baseline_test_execution: _TestExecution | None = None
    test_timeout_seconds = _resolve_test_timeout_seconds(run_input.metadata)
    repo_root = _resolve_repo_root(run_input.target_repo)
    ignore_rules = _load_ignore_rules(repo_root)
    temp_branch_context: TempBranchContext | None = None
    branch_cleanup_error: str | None = None

    try:
        mcp_servers = build_mcp_servers(target_repo=run_input.target_repo)
        mcp_server_count = len(mcp_servers)

        if run_input.test_command is not None:
            baseline_test_execution = _run_test_command(
                run_input.test_command,
                cwd=repo_root,
                timeout_seconds=test_timeout_seconds,
            )
            accumulated_logs.extend(
                [
                    "stage=baseline",
                    f"baseline_test_exit_code={baseline_test_execution.exit_code}",
                    f"baseline_test_timed_out={baseline_test_execution.timed_out}",
                    f"baseline_test_signature={baseline_test_execution.signature}",
                ]
            )

        final_message: str | None = None
        for iteration in range(1, max_iterations + 1):
            identity = build_run_identity(
                run_input=run_input,
                agent_config=resolved_settings.fingerprint_payload(),
                iteration=iteration,
                run_id=run_id,
            )
            run_id = identity.run_id

            if iteration == 1 and temp_branch_context is None and _is_git_repository(repo_root):
                branch_prefix = _resolve_temp_branch_prefix(run_input.metadata)
                temp_branch_context = _create_temp_branch(
                    repo_root,
                    run_id=run_id,
                    branch_prefix=branch_prefix,
                )
                accumulated_logs.extend(
                    [
                        "stage=git",
                        f"git_original_branch={temp_branch_context.original_branch}",
                        f"git_temp_branch={temp_branch_context.branch_name}",
                    ]
                )

            before_snapshot = _snapshot_repo_state(repo_root)

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

            after_snapshot = _snapshot_repo_state(repo_root)
            changed_files = _detect_changed_files(before_snapshot, after_snapshot)
            repo_changed = len(changed_files) > 0
            test_execution = _run_test_command(
                run_input.test_command,
                cwd=repo_root,
                timeout_seconds=test_timeout_seconds,
            )
            latest_tests = _to_test_results(test_execution)
            latest_artifacts = _persist_iteration_artifacts(
                repo_root=repo_root,
                run_id=identity.run_id,
                iteration=iteration,
                diff=latest_diff,
                changed_files=changed_files,
                temp_branch=temp_branch_context.branch_name if temp_branch_context is not None else None,
                ignore_rules=ignore_rules,
            )

            diff_integrity_ok, diff_integrity_reason = _validate_diff_integrity(
                changed_files=changed_files,
                diff=latest_diff,
            )
            if not diff_integrity_ok:
                branch_cleanup_error = _restore_temp_branch_for_debug(
                    repo_root=repo_root,
                    temp_branch_context=temp_branch_context,
                    accumulated_logs=accumulated_logs,
                )
                accumulated_logs.extend(
                    [
                        "stage=validation",
                        "validation_result=diff_integrity_failure",
                        f"validation_reason={diff_integrity_reason}",
                    ]
                )
                return RunOutput(
                    identity=identity,
                    status=RunStatus.FAILED,
                    stop_reason=StopReason.VALIDATION_FAILURE,
                    diff=latest_diff,
                    logs=accumulated_logs,
                    tests=latest_tests,
                    errors=[
                        RunError(
                            category=ErrorCategory.VALIDATION,
                            message="Diff integrity validation failed",
                            retryable=False,
                            details={
                                "reason": diff_integrity_reason,
                                "changed_files_count": len(changed_files),
                            },
                        )
                    ],
                    artifacts=latest_artifacts,
                    final_message=final_message,
                )

            coherence_ok, coherence_details = _validate_changed_files_coherence(
                proposal=proposal,
                changed_files=changed_files,
                repo_changed=repo_changed,
                diff=latest_diff,
            )
            if not coherence_ok:
                branch_cleanup_error = _restore_temp_branch_for_debug(
                    repo_root=repo_root,
                    temp_branch_context=temp_branch_context,
                    accumulated_logs=accumulated_logs,
                )
                accumulated_logs.extend(
                    [
                        "stage=validation",
                        "validation_result=changed_files_mismatch",
                    ]
                )
                return RunOutput(
                    identity=identity,
                    status=RunStatus.FAILED,
                    stop_reason=StopReason.VALIDATION_FAILURE,
                    diff=latest_diff,
                    logs=accumulated_logs,
                    tests=latest_tests,
                    errors=[
                        RunError(
                            category=ErrorCategory.VALIDATION,
                            message="Proposal changed_files does not match repository changes",
                            retryable=False,
                            details=coherence_details,
                        )
                    ],
                    artifacts=latest_artifacts,
                    final_message=final_message,
                )

            if baseline_test_execution is not None and _is_regression(
                baseline=baseline_test_execution,
                current=test_execution,
            ):
                branch_cleanup_error = _restore_temp_branch_for_debug(
                    repo_root=repo_root,
                    temp_branch_context=temp_branch_context,
                    accumulated_logs=accumulated_logs,
                )
                accumulated_logs.extend(
                    [
                        "stage=validation",
                        "validation_result=regression_detected",
                        "validation_rule=baseline_exit_code==0_and_current_exit_code!=0",
                        f"validation_baseline_exit_code={baseline_test_execution.exit_code}",
                        f"validation_current_exit_code={test_execution.exit_code}",
                    ]
                )
                return RunOutput(
                    identity=identity,
                    status=RunStatus.FAILED,
                    stop_reason=StopReason.VALIDATION_FAILURE,
                    diff=latest_diff,
                    logs=accumulated_logs,
                    tests=latest_tests,
                    errors=[
                        RunError(
                            category=ErrorCategory.VALIDATION,
                            message="Regression detected against baseline test execution",
                            retryable=False,
                            details={
                                "rule": "baseline_exit_code==0_and_current_exit_code!=0",
                                "baseline_exit_code": baseline_test_execution.exit_code,
                                "current_exit_code": test_execution.exit_code,
                            },
                        )
                    ],
                    artifacts=latest_artifacts,
                    final_message=final_message,
                )

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
                branch_cleanup_error = _restore_temp_branch_for_debug(
                    repo_root=repo_root,
                    temp_branch_context=temp_branch_context,
                    accumulated_logs=accumulated_logs,
                )
                return RunOutput(
                    identity=identity,
                    status=RunStatus.PARTIAL,
                    stop_reason=StopReason.NO_PROGRESS,
                    diff=latest_diff,
                    logs=accumulated_logs,
                    tests=latest_tests,
                    artifacts=latest_artifacts,
                    final_message=final_message,
                )

            previous_proposal_signature = _proposal_signature(proposal)
            previous_test_signature = test_execution.signature

            if _can_complete_early(run_input=run_input, test_execution=test_execution):
                if temp_branch_context is not None:
                    try:
                        _restore_original_branch(repo_root, original_branch=temp_branch_context.original_branch)
                        _delete_branch(repo_root, branch_name=temp_branch_context.branch_name)
                        accumulated_logs.extend(
                            [
                                "stage=git",
                                "git_branch_cleanup=deleted_on_success",
                            ]
                        )
                    except RuntimeError as exc:
                        branch_cleanup_error = str(exc)
                if branch_cleanup_error:
                    accumulated_logs.extend(
                        [
                            "stage=git",
                            "git_branch_cleanup=failed_on_success",
                            f"git_branch_cleanup_error={branch_cleanup_error}",
                        ]
                    )
                    return RunOutput(
                        identity=identity,
                        status=RunStatus.FAILED,
                        stop_reason=StopReason.INFRA_FAILURE,
                        diff=latest_diff,
                        logs=accumulated_logs,
                        tests=latest_tests,
                        errors=[
                            RunError(
                                category=ErrorCategory.INFRA,
                                message="Temporary branch cleanup failed after successful validation",
                                retryable=False,
                                details={
                                    "branch_cleanup_error": branch_cleanup_error,
                                    "temp_branch": (
                                        temp_branch_context.branch_name if temp_branch_context is not None else None
                                    ),
                                },
                            )
                        ],
                        artifacts=latest_artifacts,
                        final_message=final_message,
                    )
                return RunOutput(
                    identity=identity,
                    status=RunStatus.SUCCESS,
                    stop_reason=StopReason.COMPLETED,
                    diff=latest_diff,
                    logs=accumulated_logs,
                    tests=latest_tests,
                    artifacts=latest_artifacts,
                    final_message=final_message,
                )

        assert final_message is not None
        branch_cleanup_error = _restore_temp_branch_for_debug(
            repo_root=repo_root,
            temp_branch_context=temp_branch_context,
            accumulated_logs=accumulated_logs,
        )
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
            artifacts=latest_artifacts,
            final_message=final_message,
        )
    except Exception as exc:
        if temp_branch_context is not None:
            try:
                _restore_original_branch(repo_root, original_branch=temp_branch_context.original_branch)
                accumulated_logs.extend(
                    [
                        "stage=git",
                        f"git_branch_cleanup=kept_for_debug:{temp_branch_context.branch_name}",
                    ]
                )
            except RuntimeError as restore_exc:
                branch_cleanup_error = str(restore_exc)
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
                    message=_format_failure_message(exc, branch_cleanup_error),
                    retryable=False,
                    details={"provider": resolved_settings.provider.value},
                )
            ],
            artifacts=latest_artifacts,
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


def _resolve_temp_branch_prefix(metadata: dict[str, Any]) -> str:
    value = metadata.get("temp_branch_prefix")
    if value is None:
        return "autofix"
    if not isinstance(value, str):
        raise ValueError("metadata.temp_branch_prefix must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("metadata.temp_branch_prefix cannot be empty")
    return normalized


def _format_failure_message(exc: Exception, branch_cleanup_error: str | None) -> str:
    if not branch_cleanup_error:
        return str(exc)
    return f"{exc}; branch_cleanup_error={branch_cleanup_error}"


def _restore_temp_branch_for_debug(
    *,
    repo_root: Path,
    temp_branch_context: TempBranchContext | None,
    accumulated_logs: list[str],
) -> str | None:
    if temp_branch_context is None:
        return None
    try:
        _restore_original_branch(repo_root, original_branch=temp_branch_context.original_branch)
        accumulated_logs.extend(
            [
                "stage=git",
                f"git_branch_cleanup=kept_for_debug:{temp_branch_context.branch_name}",
            ]
        )
        return None
    except RuntimeError as restore_exc:
        accumulated_logs.extend(
            [
                "stage=git",
                "git_branch_cleanup=restore_failed",
                f"git_branch_cleanup_error={restore_exc}",
            ]
        )
        return str(restore_exc)


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
