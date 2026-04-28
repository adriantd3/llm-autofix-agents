from __future__ import annotations

import logging
from pathlib import Path

from llm_autofix_agents.observability.models import (
    AgentDescriptor,
    AgentExecutionRecord,
    FileChangeRecord,
    IterationRecord,
    ProviderCallRecord,
    RunDescriptor,
    RunFinishedRecord,
    TestExecutionRecord,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)


class MarkdownLiveObserver:
    def __init__(self, live_log_path: Path) -> None:
        self._path = live_log_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def on_run_started(self, *, run: RunDescriptor, started_at: str) -> None:
        content = [
            f"# Run {run.run_id}",
            "",
            f"- Architecture: {run.architecture}",
            f"- Started at: {started_at}",
            f"- Target repo: {run.target_repo or '(none)'}",
            "",
        ]
        self._path.write_text("\n".join(content), encoding="utf-8")

    def on_run_finished(self, *, run_finished: RunFinishedRecord) -> None:
        self._append(
            "\n".join(
                [
                    "",
                    "## Run finished",
                    f"- status: {run_finished.final_status}",
                    f"- stop_reason: {run_finished.stop_reason}",
                    f"- duration_seconds: {run_finished.duration_seconds:.3f}",
                    f"- total_iterations: {run_finished.total_iterations}",
                ]
            )
        )

    def on_run_agent_registered(self, *, run_id: str, agent: AgentDescriptor, instructions_hash: str | None) -> str:
        del run_id, instructions_hash
        self._append(
            "\n".join(
                [
                    "",
                    "## Agent",
                    f"- name: {agent.agent_name}",
                    f"- role: {agent.agent_role}",
                    f"- model: {agent.model_config.provider}/{agent.model_config.model}",
                    f"- tool_profile: {agent.tool_profile}",
                ]
            )
        )
        return ""

    def on_iteration_started(self, *, record: IterationRecord) -> None:
        self._append(f"\n## Iteration {record.iteration_index}\n- started_at: {record.started_at}")

    def on_iteration_finished(self, *, record: IterationRecord) -> None:
        self._append(
            "\n".join(
                [
                    "",
                    f"### Iteration {record.iteration_index} result",
                    f"- status: {record.status}",
                    f"- stop_reason: {record.stop_reason}",
                    f"- duration_seconds: {0.0 if record.duration_seconds is None else record.duration_seconds:.3f}",
                    f"- tool_calls_count: {record.tool_calls_count}",
                    f"- changed_files_count: {record.changed_files_count}",
                    f"- test_exit_code: {record.test_exit_code}",
                ]
            )
        )

    def on_agent_execution_started(self, *, record: AgentExecutionRecord) -> None:
        self._append(
            "\n".join(
                [
                    "",
                    "### Agent execution started",
                    f"- agent_execution_id: {record.agent_execution_id}",
                    f"- started_at: {record.started_at}",
                ]
            )
        )

    def on_agent_execution_finished(self, *, record: AgentExecutionRecord) -> None:
        self._append(
            "\n".join(
                [
                    "",
                    "### Agent execution finished",
                    f"- status: {record.status}",
                    f"- duration_seconds: {0.0 if record.duration_seconds is None else record.duration_seconds:.3f}",
                    f"- tool_calls_count: {record.tool_calls_count}",
                    f"- reasoning_summary: {record.reasoning_summary or ''}",
                ]
            )
        )

    def on_tool_call(self, *, record: ToolCallRecord) -> None:
        self._append(f"- tool {record.seq:03d}: {record.tool_name} -> {record.status or 'unknown'}")

    def on_provider_call_event(self, *, record: ProviderCallRecord) -> None:
        self._append(_format_provider_call_record(record))

    def on_test_execution(self, *, record: TestExecutionRecord) -> None:
        self._append(
            "- test phase="
            f"{record.phase} exit_code={record.exit_code} timed_out={record.timed_out} "
            f"signature={record.signature}"
        )

    def on_file_change(self, *, record: FileChangeRecord) -> None:
        self._append(f"- file_change: {record.path} ({record.change_type or 'modified'})")

    def _append(self, text: str) -> None:
        with self._path.open("a", encoding="utf-8") as handler:
            handler.write(f"{text}\n")


class ConsoleObserver:
    def on_run_started(self, *, run: RunDescriptor, started_at: str) -> None:
        logger.info("[run] started %s at %s", run.run_id, started_at)

    def on_run_finished(self, *, run_finished: RunFinishedRecord) -> None:
        logger.info("[run] finished status=%s stop_reason=%s", run_finished.final_status, run_finished.stop_reason)

    def on_run_agent_registered(self, *, run_id: str, agent: AgentDescriptor, instructions_hash: str | None) -> str:
        del run_id, instructions_hash
        logger.info("[agent] registered %s/%s", agent.agent_name, agent.agent_role)
        return ""

    def on_iteration_started(self, *, record: IterationRecord) -> None:
        logger.info("[it %s] started", record.iteration_index)

    def on_iteration_finished(self, *, record: IterationRecord) -> None:
        logger.info("[it %s] finished status=%s tokens=%s", record.iteration_index, record.status, record.total_tokens)

    def on_agent_execution_started(self, *, record: AgentExecutionRecord) -> None:
        logger.info("[agent_exec] %s started", record.agent_execution_id)

    def on_agent_execution_finished(self, *, record: AgentExecutionRecord) -> None:
        logger.info("[agent_exec] %s finished status=%s", record.agent_execution_id, record.status)

    def on_tool_call(self, *, record: ToolCallRecord) -> None:
        logger.info("[tool] %s -> %s", record.tool_name, record.status or "unknown")

    def on_provider_call_event(self, *, record: ProviderCallRecord) -> None:
        logger.info(_format_provider_call_record(record))

    def on_test_execution(self, *, record: TestExecutionRecord) -> None:
        logger.info("[test:%s] exit_code=%s timed_out=%s", record.phase, record.exit_code, record.timed_out)

    def on_file_change(self, *, record: FileChangeRecord) -> None:
        logger.info("[file] %s %s", record.path, record.change_type or "modified")


def _format_provider_call_record(record: ProviderCallRecord) -> str:
    status_code = record.status_code if record.status_code is not None else "unknown"
    tool_calls = record.tool_calls_count if record.tool_calls_count is not None else "unknown"
    delay = ""
    if record.retry_delay_seconds is not None:
        delay = f" retry_in={record.retry_delay_seconds:.3f}s"

    if record.event_type == "retryable_failure":
        return (
            f"- provider retryable failure attempt={record.attempt}/{record.total_attempts} "
            f"status_code={status_code} error_type={record.error_type or 'unknown'} "
            f"tool_calls_before_retry={tool_calls} rerun_full_runner={record.rerun_full_runner}"
        )
    if record.event_type == "retry_scheduled":
        return (
            f"- provider retry scheduled attempt={record.attempt}/{record.total_attempts} "
            f"status_code={status_code} error_type={record.error_type or 'unknown'} "
            f"tool_calls_before_retry={tool_calls}{delay} rerun_full_runner={record.rerun_full_runner}"
        )
    if record.event_type == "retry_succeeded":
        return (
            f"- provider retry recovered attempt={record.attempt}/{record.total_attempts} "
            f"tool_calls_seen={tool_calls} rerun_full_runner={record.rerun_full_runner}"
        )
    if record.event_type == "retries_exhausted":
        return (
            f"- provider retries exhausted attempt={record.attempt}/{record.total_attempts} "
            f"status_code={status_code} error_type={record.error_type or 'unknown'} "
            f"tool_calls_before_failure={tool_calls} rerun_full_runner={record.rerun_full_runner}"
        )
    if record.event_type == "non_retryable_failure":
        return (
            f"- provider non-retryable failure attempt={record.attempt}/{record.total_attempts} "
            f"status_code={status_code} error_type={record.error_type or 'unknown'} "
            f"tool_calls_before_failure={tool_calls} rerun_full_runner={record.rerun_full_runner}"
        )
    return (
        f"- provider event {record.event_type} attempt={record.attempt}/{record.total_attempts} "
        f"status_code={status_code} error_type={record.error_type or 'unknown'}"
    )
