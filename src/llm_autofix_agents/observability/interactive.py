from __future__ import annotations

import json
import logging
from pathlib import Path

from llm_autofix_agents.observability.events import (
    AgentExecutionFinished,
    AgentExecutionStarted,
    AgentHandoff,
    AgentRegistered,
    FacadeInput,
    FileChanged,
    IterationFinished,
    IterationStarted,
    ObservabilityEvent,
    ProviderCallHappened,
    RunFinished,
    RunStarted,
    TestExecuted,
    ToolCalled,
)
from llm_autofix_agents.observability.models import (
    AgentHandoffRecord,
    ProviderCallRecord,
    ToolCallRecord,
)

logger = logging.getLogger(__name__)


_KV_LONG_KEYS = frozenset({"path", "cwd", "command", "cmd", "target"})
_KV_CONTENT_KEYS = frozenset({"stdout", "stderr", "answer", "content", "output", "diff"})


def _format_kv_pairs(data: dict[str, object], max_items: int = 20) -> str:
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
            if k in _KV_CONTENT_KEYS:
                cap = 500
            elif k in _KV_LONG_KEYS:
                cap = 200
            else:
                cap = 120
            if len(v) > cap:
                items.append(f"{k}={v[:cap - 3]}...")
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


_ERROR_STATUSES = frozenset({"tool_error", "sdk_error", "failed"})


def _format_tool_summary(record: ToolCallRecord) -> str:
    """Return a concise multi-line summary for a tool call in live.md."""
    status = record.status or "unknown"
    is_error = status in _ERROR_STATUSES
    prefix = f"tool {record.seq:03d}: {'[!] ' if is_error else ''}"
    parts = []
    if record.agent_name:
        parts.append(f"[{record.agent_name}]")
    parts.append(record.tool_name)
    parts.append("->")
    parts.append(status)
    if record.duration_seconds is not None:
        parts.append(f"({record.duration_seconds:.3f}s)")
    header = prefix + " ".join(parts)

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


class MarkdownLiveObserver:
    def __init__(self, live_log_path: Path) -> None:
        self._path = live_log_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def emit(self, event: ObservabilityEvent) -> None:
        match event:
            case RunStarted():
                content = [
                    f"# Run {event.run.run_id}",
                    "",
                    f"- Architecture: {event.run.architecture}",
                    f"- Started at: {event.started_at}",
                    f"- Target repo: {event.run.target_repo or '(none)'}",
                    "",
                ]
                self._path.write_text("\n".join(content), encoding="utf-8")
            case RunFinished():
                rf = event.run_finished
                self._append(
                    "\n".join([
                        "",
                        "## Run finished",
                        f"- status: {rf.final_status}",
                        f"- stop_reason: {rf.stop_reason}",
                        f"- duration_seconds: {rf.duration_seconds:.3f}",
                        f"- total_iterations: {rf.total_iterations}",
                    ])
                )
            case AgentRegistered():
                self._append(
                    "\n".join([
                        "",
                        "## Agent",
                        f"- name: {event.agent.agent_name}",
                        f"- role: {event.agent.agent_role}",
                        f"- model: {event.agent.model_config.provider}/{event.agent.model_config.model}",
                        f"- tool_profile: {event.agent.tool_profile}",
                    ])
                )
            case IterationStarted():
                r = event.record
                self._append(f"\n## Iteration {r.iteration_index}\n- started_at: {r.started_at}")
            case IterationFinished():
                r = event.record
                self._append(
                    "\n".join([
                        "",
                        f"### Iteration {r.iteration_index} result",
                        f"- status: {r.status}",
                        f"- stop_reason: {r.stop_reason}",
                        f"- duration_seconds: {0.0 if r.duration_seconds is None else r.duration_seconds:.3f}",
                        f"- tool_calls_count: {r.tool_calls_count}",
                        f"- changed_files_count: {r.changed_files_count}",
                        f"- test_exit_code: {r.test_exit_code}",
                    ])
                )
            case AgentExecutionStarted():
                r = event.record
                self._append(
                    "\n".join([
                        "",
                        "### Agent execution started",
                        f"- agent_execution_id: {r.agent_execution_id}",
                        f"- started_at: {r.started_at}",
                    ])
                )
            case AgentExecutionFinished():
                r = event.record
                self._append(
                    "\n".join([
                        "",
                        "### Agent execution finished",
                        f"- status: {r.status}",
                        f"- duration_seconds: {0.0 if r.duration_seconds is None else r.duration_seconds:.3f}",
                        f"- tool_calls_count: {r.tool_calls_count}",
                        f"- reasoning_summary: {r.reasoning_summary or ''}",
                    ])
                )
            case ToolCalled():
                self._append(_format_tool_summary(event.record))
            case ProviderCallHappened():
                self._append(_format_provider_call_record(event.record))
            case TestExecuted():
                r = event.record
                self._append(
                    "- test phase="
                    f"{r.phase} exit_code={r.exit_code} timed_out={r.timed_out} "
                    f"signature={r.signature}"
                )
            case FileChanged():
                r = event.record
                self._append(f"- file_change: {r.path} ({r.change_type or 'modified'})")
            case AgentHandoff():
                self._append(_format_handoff(event.record))
            case FacadeInput():
                r = event.record
                self._append(
                    "\n".join([
                        "",
                        f"### Facade input (iteration {r.iteration_index})",
                        "```",
                        r.input_text,
                        "```",
                    ])
                )

    def _append(self, text: str) -> None:
        with self._path.open("a", encoding="utf-8") as handler:
            handler.write(f"{text}\n")


class ConsoleObserver:
    def emit(self, event: ObservabilityEvent) -> None:
        match event:
            case RunStarted():
                logger.info("[run] started %s at %s", event.run.run_id, event.started_at)
            case RunFinished():
                rf = event.run_finished
                logger.info("[run] finished status=%s stop_reason=%s", rf.final_status, rf.stop_reason)
            case AgentRegistered():
                logger.info("[agent] registered %s/%s", event.agent.agent_name, event.agent.agent_role)
            case IterationStarted():
                logger.info("[it %s] started", event.record.iteration_index)
            case IterationFinished():
                r = event.record
                logger.info("[it %s] finished status=%s tokens=%s", r.iteration_index, r.status, r.total_tokens)
            case AgentExecutionStarted():
                logger.info("[agent_exec] %s started", event.record.agent_execution_id)
            case AgentExecutionFinished():
                logger.info("[agent_exec] %s finished status=%s", event.record.agent_execution_id, event.record.status)
            case ToolCalled():
                logger.info("[tool] %s", _format_tool_summary(event.record).replace("\n", " | "))
            case ProviderCallHappened():
                logger.info(_format_provider_call_record(event.record))
            case TestExecuted():
                r = event.record
                logger.info("[test:%s] exit_code=%s timed_out=%s", r.phase, r.exit_code, r.timed_out)
            case FileChanged():
                r = event.record
                logger.info("[file] %s %s", r.path, r.change_type or "modified")
            case AgentHandoff():
                r = event.record
                logger.info("[handoff] %s -> %s", r.from_agent_name, r.to_agent_name)
            case FacadeInput():
                r = event.record
                text = r.input_text[:200] + "..." if len(r.input_text) > 200 else r.input_text
                logger.info("[facade_input it=%s] %s", r.iteration_index, text.replace("\n", " "))
