from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def make_agent_execution_id(run_id: str, iteration: int) -> str:
    return f"{run_id}-it{iteration:02d}-agent01"


def make_test_execution_id(run_id: str, iteration: int) -> str:
    if iteration == 0:
        return f"{run_id}-baseline-test"
    return f"{run_id}-it{iteration:02d}-validation-test"


def make_file_change_id(run_id: str, iteration: int, file_index: int) -> str:
    return f"{run_id}-it{iteration:02d}-file{file_index:03d}"


@dataclass(frozen=True)
class RunDescriptor:
    run_id: str
    architecture: str
    target_repo: str | None
    target_branch: str | None
    run_fingerprint: str
    prompt_hash: str | None = None
    experiment_id: str | None = None
    benchmark_name: str | None = None
    problem_id: str | None = None


@dataclass(frozen=True)
class ModelConfigDescriptor:
    provider: str
    model: str
    max_turns: int
    base_url: str | None = None
    tracing_disabled: bool = True


@dataclass(frozen=True)
class AgentDescriptor:
    agent_name: str
    agent_role: str
    model_config: ModelConfigDescriptor
    tool_profile: str
    agent_order: int = 1


@dataclass(frozen=True)
class IterationRecord:
    run_id: str
    iteration_id: str
    iteration_index: int
    started_at: str
    finished_at: str | None = None
    duration_seconds: float | None = None
    status: str | None = None
    stop_reason: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tool_calls_count: int = 0
    changed_files_count: int = 0
    repo_changed: bool = False
    test_exit_code: int | None = None
    test_timed_out: bool | None = None
    test_signature: str | None = None

    @classmethod
    def started(cls, run_id: str, iteration_id: str, iteration_index: int) -> "IterationRecord":
        return cls(
            run_id=run_id,
            iteration_id=iteration_id,
            iteration_index=iteration_index,
            started_at=utc_now_iso(),
            status="started",
        )

    @classmethod
    def finished(
        cls,
        run_id: str,
        iteration_id: str,
        iteration_index: int,
        started_at: str,
        status: str | None = None,
        stop_reason: str | None = None,
        duration_seconds: float | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        tool_calls_count: int = 0,
        changed_files_count: int = 0,
        repo_changed: bool = False,
        test_exit_code: int | None = None,
        test_timed_out: bool | None = None,
        test_signature: str | None = None,
    ) -> "IterationRecord":
        return cls(
            run_id=run_id,
            iteration_id=iteration_id,
            iteration_index=iteration_index,
            started_at=started_at,
            finished_at=utc_now_iso(),
            status=status,
            stop_reason=stop_reason,
            duration_seconds=duration_seconds,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tool_calls_count=tool_calls_count,
            changed_files_count=changed_files_count,
            repo_changed=repo_changed,
            test_exit_code=test_exit_code,
            test_timed_out=test_timed_out,
            test_signature=test_signature,
        )


@dataclass(frozen=True)
class AgentExecutionRecord:
    agent_execution_id: str
    run_id: str
    iteration_id: str
    run_agent_id: str
    execution_index: int
    started_at: str
    finished_at: str | None = None
    duration_seconds: float | None = None
    status: str | None = None
    reasoning_summary: str | None = None
    confidence: float | None = None
    notes: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tool_calls_count: int = 0
    error_type: str | None = None
    error_message_short: str | None = None

    @classmethod
    def started(
        cls,
        agent_execution_id: str,
        run_id: str,
        iteration_id: str,
        run_agent_id: str,
        execution_index: int = 1,
    ) -> "AgentExecutionRecord":
        return cls(
            agent_execution_id=agent_execution_id,
            run_id=run_id,
            iteration_id=iteration_id,
            run_agent_id=run_agent_id,
            execution_index=execution_index,
            started_at=utc_now_iso(),
            status="running",
        )

    @classmethod
    def finished(
        cls,
        agent_execution_id: str,
        run_id: str,
        iteration_id: str,
        run_agent_id: str,
        execution_index: int,
        started_at: str,
        status: str | None = None,
        reasoning_summary: str | None = None,
        confidence: float | None = None,
        notes: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        tool_calls_count: int = 0,
        error_type: str | None = None,
        error_message_short: str | None = None,
    ) -> "AgentExecutionRecord":
        return cls(
            agent_execution_id=agent_execution_id,
            run_id=run_id,
            iteration_id=iteration_id,
            run_agent_id=run_agent_id,
            execution_index=execution_index,
            started_at=started_at,
            finished_at=utc_now_iso(),
            status=status,
            reasoning_summary=reasoning_summary,
            confidence=confidence,
            notes=notes,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            tool_calls_count=tool_calls_count,
            error_type=error_type,
            error_message_short=error_message_short,
        )


@dataclass(frozen=True)
class ToolCallRecord:
    tool_call_id: str
    run_id: str
    iteration_id: str
    agent_execution_id: str | None
    seq: int
    tool_name: str
    status: str | None
    success: bool | None


@dataclass(frozen=True)
class TestExecutionRecord:
    test_execution_id: str
    run_id: str
    phase: str
    iteration_id: str | None = None
    agent_execution_id: str | None = None
    tool_call_id: str | None = None
    command: str | None = None
    duration_seconds: float | None = None
    exit_code: int | None = None
    timed_out: bool | None = None
    tests_total: int | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    output_path: str | None = None
    signature: str | None = None

    @classmethod
    def create(
        cls,
        test_execution_id: str,
        run_id: str,
        phase: str,
        command: str | None = None,
        exit_code: int | None = None,
        timed_out: bool | None = None,
        signature: str | None = None,
        iteration_id: str | None = None,
        agent_execution_id: str | None = None,
    ) -> "TestExecutionRecord":
        return cls(
            test_execution_id=test_execution_id,
            run_id=run_id,
            phase=phase,
            command=command,
            exit_code=exit_code,
            timed_out=timed_out,
            signature=signature,
            iteration_id=iteration_id,
            agent_execution_id=agent_execution_id,
        )


@dataclass(frozen=True)
class FileChangeRecord:
    file_change_id: str
    run_id: str
    path: str
    change_type: str | None
    iteration_id: str | None = None
    agent_execution_id: str | None = None
    tool_call_id: str | None = None
    additions: int | None = None
    deletions: int | None = None
    detected_by: str | None = None

    @classmethod
    def create(
        cls,
        file_change_id: str,
        run_id: str,
        path: str,
        change_type: str,
        detected_by: str | None = None,
        iteration_id: str | None = None,
        agent_execution_id: str | None = None,
    ) -> "FileChangeRecord":
        return cls(
            file_change_id=file_change_id,
            run_id=run_id,
            path=path,
            change_type=change_type,
            detected_by=detected_by,
            iteration_id=iteration_id,
            agent_execution_id=agent_execution_id,
        )


@dataclass(frozen=True)
class RunFinishedRecord:
    run_id: str
    finished_at: str
    final_status: str
    stop_reason: str
    duration_seconds: float
    total_iterations: int
    total_input_tokens: int
    total_output_tokens: int
    total_tokens: int
    files_changed_count: int
    resolved: bool
    live_log_path: str | None = None
    summary_path: str | None = None
    diff_path: str | None = None
