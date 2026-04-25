from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Coroutine
from dataclasses import dataclass, field
from hashlib import sha256
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
from llm_autofix_agents.flow import (
    TestExecution,
)
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
from llm_autofix_agents.flow.git_ops import TempBranchContext
from llm_autofix_agents.flow.iteration import _proposal_signature
from llm_autofix_agents.llm.provider import AgentFixIterationRecord, LLMProvider, create_provider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability import (
    AgentDescriptor,
    AgentExecutionRecord,
    CompositeObserver,
    ConsoleObserver,
    FileChangeRecord,
    IterationRecord,
    MarkdownLiveObserver,
    ModelConfigDescriptor,
    NullObserver,
    RunDescriptor,
    RunObserver,
    SQLiteObservabilityStore,
    TestExecutionRecord,
    make_file_change_id,
    make_test_execution_id,
    resolve_observability_config,
    utc_now_iso,
    write_summary,
)
from llm_autofix_agents.tools import APRToolContext, build_apr_tools

_BASELINE_INSTRUCTIONS = (
    "You are an APR baseline agent operating autonomously. "
    "Decide the flow using the available local APR tools, avoid hardcoded assumptions, "
    "run commands through the local command tool when validation is needed, "
    "apply and validate changes directly in the target repository via local tools, "
    "and then return a structured iteration report with: "
    "status, reasoning_summary, confidence, changed_files, notes."
)

logger = logging.getLogger(__name__)


@dataclass
class RunState:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    max_changed_files_count: int = 0
    accumulated_logs: list[str] = field(default_factory=list)
    final_message: str | None = None
    latest_tests: TestResults | None = None
    latest_diff: str = ""
    latest_artifacts: dict[str, Any] = field(default_factory=dict)
    latest_proposal_changed_files: list[str] = field(default_factory=list)
    latest_changed_files: list[str] = field(default_factory=list)
    previous_proposal_signature: str | None = None
    previous_proposal_status: str | None = None
    previous_proposal_confidence: float | None = None
    previous_test_signature: str | None = None


def run_agent_baseline(
    run_input: RunInput,
    *,
    settings: LLMSettings | None = None,
    provider: LLMProvider | None = None,
) -> RunOutput:
    resolved_settings = settings if settings is not None else LLMSettings.from_env()
    resolved_provider = provider if provider is not None else create_provider(resolved_settings)
    max_iterations = _resolve_max_iterations(run_input.metadata)
    tool_profile = _resolve_tool_profile(run_input.metadata)

    state, cfg = _initialize_run(run_input, resolved_settings, resolved_provider, tool_profile, max_iterations)

    try:
        baseline_test_execution = _run_baseline_test_if_needed(run_input, state, cfg)

        for iteration in range(1, max_iterations + 1):
            output = _execute_iteration(run_input, state, cfg, iteration, baseline_test_execution, max_iterations)
            if output is not None:
                return output

        return _finish_max_iterations(run_input, state, cfg)

    except Exception as exc:
        return _handle_run_exception(exc, run_input, state, cfg)


@dataclass
class RunConfig:
    run_id: str
    run_agent_id: str
    settings: LLMSettings
    provider: LLMProvider
    agent_context: APRToolContext
    agent_tools: list[object]
    tool_profile: str
    max_iterations: int
    test_timeout_seconds: int
    repo_root: Path
    test_command: str | None
    ignore_rules: list[str]
    baseline_test_execution: TestExecution | None = None
    temp_branch: TempBranchContext | None = None
    observer: RunObserver | None = None
    sqlite_store: SQLiteObservabilityStore | None = None
    live_observer: MarkdownLiveObserver | None = None
    run_input: RunInput | None = None
    agent_config: dict = field(default_factory=dict)
    baseline_instructions: str = ""
    run_started_monotonic: float = 0.0


def _initialize_run(
    run_input: RunInput,
    settings: LLMSettings,
    provider: LLMProvider,
    tool_profile: str,
    max_iterations: int,
) -> tuple[RunState, RunConfig]:
    repo_root = _resolve_repo_root(run_input.target_repo)
    agent_context = APRToolContext(root_dir=str(repo_root))
    agent_tools = build_apr_tools(tool_profile)
    test_timeout_seconds = _resolve_test_timeout_seconds(run_input.metadata)
    ignore_rules = _load_ignore_rules(repo_root)
    agent_config = {**settings.fingerprint_payload(), "tool_profile": tool_profile}

    identity = build_run_identity(run_input=run_input, agent_config=agent_config, iteration=1)
    run_id = identity.run_id
    run_started_monotonic = time.perf_counter()
    run_started_at = utc_now_iso()

    obs_config = resolve_observability_config(repo_root=repo_root, metadata=run_input.metadata)
    observer, sqlite_store, live_observer = _build_observer(obs_config, repo_root, run_id)

    observer.on_run_started(
        run=RunDescriptor(
            run_id=run_id,
            architecture="mono_agent",
            target_repo=run_input.target_repo,
            target_branch=_metadata_text(run_input.metadata, "runtime_branch"),
            run_fingerprint=identity.run_fingerprint,
            prompt_hash=sha256(run_input.prompt.encode("utf-8")).hexdigest()[:16],
            benchmark_name=_metadata_text(run_input.metadata, "benchmark_name"),
            problem_id=_metadata_text(run_input.metadata, "problem_id"),
        ),
        started_at=run_started_at,
    )

    run_agent_id = observer.on_run_agent_registered(
        run_id=run_id,
        agent=AgentDescriptor(
            agent_name="baseline",
            agent_role="fixer",
            model_config=ModelConfigDescriptor(
                provider=settings.provider.value,
                model=settings.model,
                max_turns=settings.max_turns,
                base_url=settings.base_url,
                tracing_disabled=settings.tracing_disabled,
            ),
            tool_profile=tool_profile,
            agent_order=1,
        ),
        instructions_hash=sha256(_BASELINE_INSTRUCTIONS.encode("utf-8")).hexdigest()[:16],
    )
    if not run_agent_id:
        run_agent_id = f"{run_id}-agent-baseline"

    cfg = RunConfig(
        run_id=run_id,
        run_agent_id=run_agent_id,
        settings=settings,
        provider=provider,
        agent_context=agent_context,
        agent_tools=agent_tools,
        tool_profile=tool_profile,
        max_iterations=max_iterations,
        test_timeout_seconds=test_timeout_seconds,
        repo_root=repo_root,
        test_command=run_input.test_command,
        ignore_rules=ignore_rules,
        observer=observer,
        sqlite_store=sqlite_store,
        live_observer=live_observer,
        run_input=run_input,
        agent_config=agent_config,
        baseline_instructions=_BASELINE_INSTRUCTIONS,
        run_started_monotonic=run_started_monotonic,
    )

    return RunState(), cfg


def _build_observer(
    config, repo_root: Path, run_id: str
) -> tuple[RunObserver, SQLiteObservabilityStore | None, MarkdownLiveObserver | None]:
    from llm_autofix_agents.observability import SQLiteObserver

    observers: list[RunObserver] = []
    sqlite_store: SQLiteObservabilityStore | None = None
    live_observer: MarkdownLiveObserver | None = None

    if config.enabled:
        sqlite_store = SQLiteObservabilityStore(db_path=config.sqlite_db_path)
        sqlite_store.initialize()
        observers.append(SQLiteObserver(sqlite_store, architecture_name="mono_agent"))
        if config.live_log_enabled:
            live_observer = MarkdownLiveObserver(config.results_dir / run_id / "live.md")
            observers.append(live_observer)
        if config.interactive:
            observers.append(ConsoleObserver())

    return (CompositeObserver(observers) if observers else NullObserver()), sqlite_store, live_observer


def _run_baseline_test_if_needed(run_input: RunInput, state: RunState, cfg: RunConfig) -> TestExecution | None:
    if run_input.test_command is None:
        return None

    test_execution = _run_test_command(
        run_input.test_command, cwd=cfg.repo_root, timeout_seconds=cfg.test_timeout_seconds
    )
    _emit_test_execution(
        observer=cfg.observer,
        run_id=cfg.run_id,
        phase="baseline",
        test_execution=test_execution,
        command=run_input.test_command,
        iteration=0,
    )
    state.accumulated_logs.extend(
        [
            f"baseline_test_exit_code={test_execution.exit_code}",
            f"baseline_test_signature={test_execution.signature}",
        ]
    )
    return test_execution


def _execute_iteration(
    run_input: RunInput,
    state: RunState,
    cfg: RunConfig,
    iteration: int,
    baseline_test_execution: TestExecution | None,
    max_iterations: int,
) -> RunOutput | None:
    from llm_autofix_agents.observability import AgentExecutionRecord, APRRunHooks

    identity = build_run_identity(
        run_input=run_input, agent_config=cfg.agent_config, iteration=iteration, run_id=cfg.run_id
    )
    iteration_started_at = utc_now_iso()
    iteration_started_monotonic = time.perf_counter()

    _emit_iteration_started(
        observer=cfg.observer,
        run_id=cfg.run_id,
        iteration_id=identity.iteration_id,
        iteration_index=iteration,
    )

    if iteration == 1 and cfg.temp_branch is None and _is_git_repository(cfg.repo_root):
        cfg.temp_branch = _create_temp_branch(
            cfg.repo_root, run_id=cfg.run_id, branch_prefix=_resolve_temp_branch_prefix(run_input.metadata)
        )
        state.accumulated_logs.extend(
            [
                f"git_original_branch={cfg.temp_branch.original_branch}",
                f"git_temp_branch={cfg.temp_branch.branch_name}",
            ]
        )

    before_snapshot = _snapshot_repo_state(cfg.repo_root)

    agent_execution_id = f"{cfg.run_id}-it{iteration:02d}-agent01"
    hooks = APRRunHooks(
        observer=cfg.observer,
        run_id=cfg.run_id,
        iteration_id=identity.iteration_id,
        agent_execution_id=agent_execution_id,
    )

    agent_started_at = utc_now_iso()
    agent_started_monotonic = time.perf_counter()
    cfg.observer.on_agent_execution_started(
        record=AgentExecutionRecord.started(
            agent_execution_id=agent_execution_id,
            run_id=cfg.run_id,
            iteration_id=identity.iteration_id,
            run_agent_id=cfg.run_agent_id,
        )
    )

    proposal = _run_sync(
        cfg.provider.run_prompt(
            instructions=cfg.baseline_instructions,
            user_input=_build_iteration_input(
                prompt=run_input.prompt,
                iteration=iteration,
                max_iterations=max_iterations,
                previous_message=state.final_message,
            ),
            max_turns=cfg.settings.max_turns,
            tools=cfg.agent_tools,
            context=cfg.agent_context,
            hooks=hooks,
        )
    )

    agent_duration = max(0.0, time.perf_counter() - agent_started_monotonic)
    _emit_agent_execution_finished(
        observer=cfg.observer,
        agent_execution_id=agent_execution_id,
        run_id=cfg.run_id,
        iteration_id=identity.iteration_id,
        run_agent_id=cfg.run_agent_id,
        execution_index=1,
        started_at=agent_started_at,
        proposal=proposal,
        tool_calls_count=hooks.tool_call_count,
    )

    state.total_input_tokens += proposal.input_tokens
    state.total_output_tokens += proposal.output_tokens
    state.total_tokens += proposal.total_tokens
    state.final_message = _render_final_message(proposal)
    state.latest_diff = _collect_repo_diff(cfg.repo_root)

    after_snapshot = _snapshot_repo_state(cfg.repo_root)
    changed_files = _detect_changed_files(before_snapshot, after_snapshot)
    state.latest_changed_files = changed_files
    state.latest_proposal_changed_files = list(proposal.changed_files)
    state.max_changed_files_count = max(state.max_changed_files_count, len(changed_files))
    repo_changed = len(changed_files) > 0

    test_execution = _run_test_command(
        run_input.test_command, cwd=cfg.repo_root, timeout_seconds=cfg.test_timeout_seconds
    )
    _emit_test_execution(
        observer=cfg.observer,
        run_id=cfg.run_id,
        phase="iteration_validation",
        test_execution=test_execution,
        command=run_input.test_command,
        iteration=iteration,
        iteration_id=identity.iteration_id,
        agent_execution_id=agent_execution_id,
    )
    state.latest_tests = _to_test_results(test_execution)

    _emit_file_changes(
        observer=cfg.observer,
        run_id=cfg.run_id,
        iteration=iteration,
        iteration_id=identity.iteration_id,
        agent_execution_id=agent_execution_id,
        changed_files=changed_files,
    )

    iteration_duration = max(0.0, time.perf_counter() - iteration_started_monotonic)
    _emit_iteration_finished(
        observer=cfg.observer,
        run_id=cfg.run_id,
        iteration_id=identity.iteration_id,
        iteration_index=iteration,
        started_at=iteration_started_at,
        proposal=proposal,
        duration_seconds=iteration_duration,
        tool_calls_count=hooks.tool_call_count,
        changed_files_count=len(changed_files),
        repo_changed=repo_changed,
        test_execution=test_execution,
    )

    validation_ok, failure_type = _check_validation(
        proposal, changed_files, state.latest_diff, test_execution, baseline_test_execution
    )
    if not validation_ok:
        _restore_temp_branch_for_debug(cfg, state.accumulated_logs)
        state.accumulated_logs.append(f"validation_result={failure_type}")
        return _build_validation_failure_output(identity, failure_type, state, cfg)

    if _is_no_progress(
        previous_message=state.previous_proposal_signature,
        current_message=_proposal_signature(proposal),
        previous_status=None,
        current_status=proposal.status,
        previous_confidence=None,
        current_confidence=proposal.confidence,
        previous_test_signature=state.previous_test_signature,
        current_test_signature=test_execution.signature,
        changed_files=changed_files,
    ):
        _restore_temp_branch_for_debug(cfg, state.accumulated_logs)
        return _build_output(identity, RunStatus.PARTIAL, StopReason.NO_PROGRESS, state, cfg)

    state.previous_proposal_signature = _proposal_signature(proposal)
    state.previous_proposal_confidence = proposal.confidence
    state.previous_test_signature = test_execution.signature

    state.accumulated_logs.extend(
        _build_run_logs(cfg, iteration, max_iterations, changed_files, test_execution, proposal.confidence)
    )

    if proposal.status == "done" and _can_complete_early(run_input=run_input, test_execution=test_execution):
        return _handle_success_case(identity, state, cfg)

    if proposal.status == "stuck":
        _restore_temp_branch_for_debug(cfg, state.accumulated_logs)
        state.accumulated_logs.append("iteration_result=agent_reported_stuck")
        return _build_output(identity, RunStatus.PARTIAL, StopReason.NO_PROGRESS, state, cfg)

    return None


def _check_validation(
    proposal, changed_files, diff, test_execution, baseline_test_execution
) -> tuple[bool, str | None]:
    if changed_files and not diff.strip():
        return False, "diff_integrity"
    if changed_files and sorted(proposal.changed_files) != sorted(changed_files):
        return False, "coherence"
    if baseline_test_execution and _is_regression(baseline=baseline_test_execution, current=test_execution):
        return False, "regression"
    return True, None


def _build_validation_failure_output(identity, failure_type: str, state: RunState, cfg: RunConfig) -> RunOutput:
    messages = {
        "diff_integrity": "Diff integrity validation failed",
        "coherence": "Proposal changed_files does not match repository changes",
        "regression": "Regression detected against baseline test execution",
    }
    details = {}
    if failure_type == "coherence":
        details["proposal_changed_files"] = state.latest_proposal_changed_files
        details["actual_changed_files"] = state.latest_changed_files
    elif failure_type == "diff_integrity":
        details["expected_files"] = state.latest_proposal_changed_files
    return _finalize_run(
        _build_output(
            identity,
            RunStatus.FAILED,
            StopReason.VALIDATION_FAILURE,
            state,
            cfg,
            errors=[
                RunError(
                    category=ErrorCategory.VALIDATION,
                    message=messages.get(failure_type, "Validation failed"),
                    retryable=False,
                    details=details,
                )
            ],
        ),
        state,
        cfg,
    )


def _handle_success_case(identity, state: RunState, cfg: RunConfig) -> RunOutput:
    cleanup_error: str | None = None
    if cfg.temp_branch:
        try:
            _restore_original_branch(cfg.repo_root, original_branch=cfg.temp_branch.original_branch)
            _delete_branch(cfg.repo_root, branch_name=cfg.temp_branch.branch_name)
        except RuntimeError as exc:
            cleanup_error = str(exc)

    if cleanup_error:
        return _finalize_run(
            _build_output(
                identity,
                RunStatus.FAILED,
                StopReason.INFRA_FAILURE,
                state,
                cfg,
                errors=[
                    RunError(
                        category=ErrorCategory.INFRA,
                        message="Branch cleanup failed",
                        retryable=False,
                        details={"branch_cleanup_error": cleanup_error},
                    )
                ],
            ),
            state,
            cfg,
        )

    return _finalize_run(_build_output(identity, RunStatus.SUCCESS, StopReason.COMPLETED, state, cfg), state, cfg)


def _finish_max_iterations(run_input: RunInput, state: RunState, cfg: RunConfig) -> RunOutput:
    _restore_temp_branch_for_debug(cfg, state.accumulated_logs)
    identity = build_run_identity(
        run_input=run_input, agent_config=cfg.agent_config, iteration=cfg.max_iterations, run_id=cfg.run_id
    )
    return _finalize_run(_build_output(identity, RunStatus.PARTIAL, StopReason.MAX_ITERATIONS, state, cfg), state, cfg)


def _handle_run_exception(exc: Exception, run_input: RunInput, state: RunState, cfg: RunConfig) -> RunOutput:
    if cfg.temp_branch:
        try:
            _restore_original_branch(cfg.repo_root, original_branch=cfg.temp_branch.original_branch)
        except RuntimeError:
            pass

    failure_identity = build_run_identity(
        run_input=run_input, agent_config=cfg.agent_config, iteration=1, run_id=cfg.run_id
    )
    return _finalize_run(
        _build_output(
            failure_identity,
            RunStatus.FAILED,
            StopReason.INFRA_FAILURE,
            state,
            cfg,
            errors=[RunError(category=ErrorCategory.MODEL, message=str(exc), retryable=False)],
        ),
        state,
        cfg,
    )


def _build_output(
    identity,
    status: RunStatus,
    stop_reason: StopReason,
    state: RunState,
    cfg: RunConfig,
    errors: list[RunError] | None = None,
) -> RunOutput:
    return RunOutput(
        identity=identity,
        status=status,
        stop_reason=stop_reason,
        diff=state.latest_diff,
        logs=state.accumulated_logs,
        tests=state.latest_tests,
        errors=errors or [],
        artifacts=state.latest_artifacts,
        final_message=state.final_message,
    )


def _finalize_run(output: RunOutput, state: RunState, cfg: RunConfig) -> RunOutput:
    from llm_autofix_agents.observability import RunFinishedRecord

    duration = max(0.0, time.perf_counter() - cfg.run_started_monotonic)
    summary_path = cfg.repo_root / "results" / cfg.run_id / "summary.json"

    write_summary(
        summary_path=summary_path,
        run_id=cfg.run_id,
        status=output.status.value,
        stop_reason=output.stop_reason.value,
        duration_seconds=duration,
        iterations=output.identity.iteration,
        input_tokens=state.total_input_tokens,
        output_tokens=state.total_output_tokens,
        total_tokens=state.total_tokens,
        changed_files_count=state.max_changed_files_count,
        observability_db=cfg.sqlite_store.db_path.relative_to(cfg.repo_root).as_posix()
        if cfg.sqlite_store
        else "disabled",
        live_log=cfg.live_observer.path.relative_to(cfg.repo_root).as_posix() if cfg.live_observer else None,
    )

    cfg.observer.on_run_finished(
        run_finished=RunFinishedRecord(
            run_id=cfg.run_id,
            finished_at=utc_now_iso(),
            final_status=output.status.value,
            stop_reason=output.stop_reason.value,
            duration_seconds=duration,
            total_iterations=output.identity.iteration,
            total_input_tokens=state.total_input_tokens,
            total_output_tokens=state.total_output_tokens,
            total_tokens=state.total_tokens,
            files_changed_count=state.max_changed_files_count,
            resolved=output.status == RunStatus.SUCCESS,
            live_log_path=cfg.live_observer.path.relative_to(cfg.repo_root).as_posix() if cfg.live_observer else None,
            summary_path=summary_path.relative_to(cfg.repo_root).as_posix(),
        )
    )

    output.artifacts = {
        **output.artifacts,
        "observability": {
            "backend": "sqlite" if cfg.sqlite_store else "disabled",
            "db_path": cfg.sqlite_store.db_path.relative_to(cfg.repo_root).as_posix()
            if cfg.sqlite_store
            else "disabled",
        },
    }
    output.logs.extend(
        [
            "stage=observability",
            f"observability_backend={'sqlite' if cfg.sqlite_store else 'disabled'}",
            f"observability_duration_seconds={duration:.3f}",
            f"observability_total_tokens={state.total_tokens}",
        ]
    )
    logger.info("completed run_id=%s status=%s", cfg.run_id, output.status.value)
    return output


def _build_run_logs(
    cfg: RunConfig,
    iteration: int,
    max_iterations: int,
    changed_files: list[str],
    test_execution: TestExecution,
    confidence: float,
) -> list[str]:
    return [
        "stage=agent",
        f"iteration={iteration}/{max_iterations}",
        f"changed_files={len(changed_files)}",
        f"proposal_confidence={confidence:.3f}",
        f"test_exit_code={test_execution.exit_code}",
        f"test_signature={test_execution.signature}",
        "toolset=apr-local",
        f"tool_profile={cfg.tool_profile}",
        f"tool_count={len(cfg.agent_tools)}",
        f"provider={cfg.settings.provider.value}",
        f"model={cfg.settings.model}",
    ]


def _restore_temp_branch_for_debug(cfg: RunConfig, logs: list[str]) -> None:
    if cfg.temp_branch is None:
        return
    try:
        _restore_original_branch(cfg.repo_root, original_branch=cfg.temp_branch.original_branch)
        logs.append(f"git_branch_cleanup=kept_for_debug:{cfg.temp_branch.branch_name}")
    except RuntimeError:
        pass


def _render_final_message(proposal: AgentFixIterationRecord) -> str:
    files = ", ".join(proposal.changed_files) if proposal.changed_files else "(unspecified)"
    lines = [
        f"status: {proposal.status}",
        f"reasoning_summary: {proposal.reasoning_summary}",
        f"confidence: {proposal.confidence:.3f}",
        f"changed_files: {files}",
    ]
    if proposal.notes:
        lines.append(f"notes: {proposal.notes}")
    return "\n".join(lines)


def _resolve_max_iterations(metadata: dict[str, Any]) -> int:
    value = metadata.get("max_iterations")
    if value is None:
        return 3
    if not isinstance(value, int) or value < 1 or value > 3:
        raise ValueError("metadata.max_iterations must be 1-3")
    return value


def _resolve_tool_profile(metadata: dict[str, Any]) -> str:
    value = metadata.get("tool_profile")
    if value is None:
        return "full"
    normalized = value.strip().lower()
    if normalized not in {"minimal", "core", "full"}:
        raise ValueError("metadata.tool_profile must be minimal/core/full")
    return normalized


def _resolve_temp_branch_prefix(metadata: dict[str, Any]) -> str:
    value = metadata.get("temp_branch_prefix")
    if value is None:
        return "autofix"
    normalized = value.strip()
    if not normalized:
        raise ValueError("metadata.temp_branch_prefix cannot be empty")
    return normalized


def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str):
        return value.strip() or None
    return None


def _run_sync(awaitable: Coroutine[object, object, AgentFixIterationRecord]) -> AgentFixIterationRecord:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("Cannot be called from an active event loop")


def _emit_test_execution(
    observer: RunObserver,
    run_id: str,
    phase: str,
    test_execution: TestExecution,
    command: str | None,
    iteration: int,
    iteration_id: str | None = None,
    agent_execution_id: str | None = None,
) -> None:
    observer.on_test_execution(
        record=TestExecutionRecord.create(
            test_execution_id=make_test_execution_id(run_id, iteration),
            run_id=run_id,
            phase=phase,
            command=command,
            exit_code=test_execution.exit_code,
            timed_out=test_execution.timed_out,
            signature=test_execution.signature,
            iteration_id=iteration_id,
            agent_execution_id=agent_execution_id,
        )
    )


def _emit_file_changes(
    observer: RunObserver,
    run_id: str,
    iteration: int,
    iteration_id: str,
    agent_execution_id: str,
    changed_files: list[str],
) -> None:
    for index, path in enumerate(changed_files, start=1):
        observer.on_file_change(
            record=FileChangeRecord.create(
                file_change_id=make_file_change_id(run_id, iteration, index),
                run_id=run_id,
                path=path,
                change_type="modified",
                detected_by="snapshot_diff",
                iteration_id=iteration_id,
                agent_execution_id=agent_execution_id,
            )
        )


def _emit_iteration_finished(
    observer: RunObserver,
    run_id: str,
    iteration_id: str,
    iteration_index: int,
    started_at: str,
    proposal: AgentFixIterationRecord,
    duration_seconds: float,
    tool_calls_count: int,
    changed_files_count: int,
    repo_changed: bool,
    test_execution: TestExecution,
) -> None:
    observer.on_iteration_finished(
        record=IterationRecord.finished(
            run_id=run_id,
            iteration_id=iteration_id,
            iteration_index=iteration_index,
            started_at=started_at,
            status=proposal.status,
            duration_seconds=duration_seconds,
            input_tokens=proposal.input_tokens,
            output_tokens=proposal.output_tokens,
            total_tokens=proposal.total_tokens,
            tool_calls_count=tool_calls_count,
            changed_files_count=changed_files_count,
            repo_changed=repo_changed,
            test_exit_code=test_execution.exit_code,
            test_timed_out=test_execution.timed_out,
            test_signature=test_execution.signature,
        )
    )


def _emit_iteration_started(
    observer: RunObserver,
    run_id: str,
    iteration_id: str,
    iteration_index: int,
) -> None:
    observer.on_iteration_started(
        record=IterationRecord.started(
            run_id=run_id,
            iteration_id=iteration_id,
            iteration_index=iteration_index,
        )
    )


def _emit_agent_execution_finished(
    observer: RunObserver,
    agent_execution_id: str,
    run_id: str,
    iteration_id: str,
    run_agent_id: str,
    execution_index: int,
    started_at: str,
    proposal: AgentFixIterationRecord,
    tool_calls_count: int,
) -> None:
    observer.on_agent_execution_finished(
        record=AgentExecutionRecord.finished(
            agent_execution_id=agent_execution_id,
            run_id=run_id,
            iteration_id=iteration_id,
            run_agent_id=run_agent_id,
            execution_index=execution_index,
            started_at=started_at,
            status=proposal.status,
            reasoning_summary=proposal.reasoning_summary,
            confidence=proposal.confidence,
            notes=proposal.notes,
            input_tokens=proposal.input_tokens,
            output_tokens=proposal.output_tokens,
            total_tokens=proposal.total_tokens,
            tool_calls_count=tool_calls_count,
        )
    )
