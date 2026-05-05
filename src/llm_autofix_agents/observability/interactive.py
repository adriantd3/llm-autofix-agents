from __future__ import annotations

import json
import logging
from pathlib import Path

from llm_autofix_agents.observability.models import (
    AgentDescriptor,
    AgentExecutionRecord,
    AgentHandoffRecord,
    FileChangeRecord,
    IterationRecord,
    ProviderCallRecord,
    RunDescriptor,
    RunFinishedRecord,
    TestExecutionRecord,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)


def _format_kv_pairs(data: dict[str, object], max_items: int = 6) -> str:
    """Format a dict as compact key=value pairs, skipping None values."""
    items = []
    for k, v in data.items():
        if v is None:
            continue
        if k in ("ok", "tool"):
            continue
        if isinstance(v, bool):
            items.append(f"{k}={v}")
        elif isinstance(v, (int, float)):
            items.append(f"{k}={v}")
        elif isinstance(v, str):
            if len(v) > 60:
                items.append(f"{k}={v[:57]}...")
            else:
                items.append(f"{k}={v}")
        elif isinstance(v, list):
            if len(v) <= 3:
                items.append(f"{k}={v}")
            else:
                items.append(f"{k}=[{', '.join(str(x) for x in v[:3])}...]")
        if len(items) >= max_items:
            break
    return ", ".join(items)


def _format_tool_summary(record: ToolCallRecord) -> str:
    """Return a concise multi-line summary for a tool call in live.md."""
    header_parts = [f"tool {record.seq:03d}:"]
    if record.agent_name:
        header_parts.append(f"[{record.agent_name}]")
    header_parts.append(record.tool_name)
    header_parts.append("->")
    header_parts.append(record.status or "unknown")
    if record.duration_seconds is not None:
        header_parts.append(f"({record.duration_seconds:.3f}s)")
    header = " ".join(header_parts)

    lines = [header]

    if record.args_summary_json:
        try:
            args_data = json.loads(record.args_summary_json)
            if isinstance(args_data, dict) and args_data:
                formatted = _format_kv_pairs(args_data)
                if formatted:
                    lines.append(f"  args: {formatted}")
        except (json.JSONDecodeError, TypeError):
            pass

    if record.result_summary_json:
        try:
            result_data = json.loads(record.result_summary_json)
            if isinstance(result_data, dict) and result_data:
                formatted = _format_kv_pairs(result_data)
                if formatted:
                    lines.append(f"  result: {formatted}")
        except (json.JSONDecodeError, TypeError):
            pass

    return "\n".join(lines)


def _format_handoff(record: AgentHandoffRecord) -> str:
    lines = [f"- handoff: {record.from_agent_name} -> {record.to_agent_name} (at {record.occurred_at})"]
    if record.handoff_note_json:
        try:
            note = json.loads(record.handoff_note_json)
            if isinstance(note, dict):
                if note.get("summary"):
                    lines.append(f"  - summary: {note['summary']}")
                if note.get("suspected_files"):
                    lines.append(f"  - suspected_files: {note['suspected_files']}")
                if note.get("confidence") is not None:
                    lines.append(f"  - confidence: {note['confidence']}")
                if note.get("evidence"):
                    lines.append(f"  - evidence: {note['evidence']}")
                if note.get("next_focus"):
                    lines.append(f"  - next_focus: {note['next_focus']}")
        except (json.JSONDecodeError, TypeError):
            lines.append(f"  - note: {record.handoff_note_json[:200]}")
    return "\n".join(lines)


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
        self._append(_format_tool_summary(record))

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

    def on_agent_handoff(self, *, record: AgentHandoffRecord) -> None:
        self._append(_format_handoff(record))

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
        logger.info("[tool] %s", _format_tool_summary(record).replace("\n", " | "))

    def on_provider_call_event(self, *, record: ProviderCallRecord) -> None:
        logger.info(_format_provider_call_record(record))

    def on_test_execution(self, *, record: TestExecutionRecord) -> None:
        logger.info("[test:%s] exit_code=%s timed_out=%s", record.phase, record.exit_code, record.timed_out)

    def on_file_change(self, *, record: FileChangeRecord) -> None:
        logger.info("[file] %s %s", record.path, record.change_type or "modified")

    def on_agent_handoff(self, *, record: AgentHandoffRecord) -> None:
        logger.info("[handoff] %s -> %s", record.from_agent_name, record.to_agent_name)


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
