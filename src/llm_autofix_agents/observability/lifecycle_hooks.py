from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from agents import Agent, RunContextWrapper, RunHooks

from llm_autofix_agents.observability.events import AgentHandoff, ToolCalled
from llm_autofix_agents.observability.models import AgentHandoffRecord, ToolCallRecord, make_handoff_id, utc_now_iso
from llm_autofix_agents.observability.tool_context import pending_handoff_note
from llm_autofix_agents.observability.tool_summaries import summarize_tool_args, summarize_tool_result
from llm_autofix_agents.tools.metadata import ToolStatus, classify_json_envelope
from llm_autofix_agents.tools.registry import get as _get_descriptor


def _error_info(result: str, success: bool | None) -> tuple[str | None, str | None]:
    if success is not False:
        return None, None
    try:
        payload = json.loads(result)
        if isinstance(payload, dict):
            error = payload.get("error")
            if error is not None:
                error_type = type(error).__name__ if not isinstance(error, str) else "tool_error"
                return error_type, str(error)[:500]
    except json.JSONDecodeError:
        pass
    return "tool_error", result[:500]


class APRRunHooks(RunHooks[Any]):
    def __init__(
        self,
        *,
        observer: Any,  # Observer protocol — emit(event) -> None
        run_id: str,
        iteration_id: str,
        agent_execution_id: str,
        run_agent_ids: dict[str, str] | None = None,
        iteration_index: int = 0,
    ) -> None:
        self._observer = observer
        self._run_id = run_id
        self._iteration_id = iteration_id
        self._agent_execution_id = agent_execution_id
        self._run_agent_ids: dict[str, str] = run_agent_ids or {}
        self._iteration_index = iteration_index
        self._seq = 0
        self._handoff_index = 0
        self._current_agent_name: str | None = None
        # Per-tool FIFO queue: tool_name → [(seq, started_at, retry_index), ...]
        self._pending_starts: dict[str, list[tuple[int, str, int]]] = {}
        # How many times each tool has been started (for retry_index assignment)
        self._tool_start_count: dict[str, int] = {}
        # Live context accumulator for rate-limit retry recovery
        self._retry_searches: list[str] = []
        self._retry_files_read: list[str] = []
        self._retry_edit_attempts: list[str] = []

    @property
    def tool_call_count(self) -> int:
        return self._seq

    @property
    def agent_execution_id(self) -> str:
        return self._agent_execution_id

    def _resolve_run_agent_id(self, agent_name: str) -> str | None:
        return self._run_agent_ids.get(agent_name)

    async def on_agent_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
    ) -> None:
        del context
        if agent is not None and hasattr(agent, "name"):
            self._current_agent_name = agent.name

    async def on_handoff(
        self,
        context: RunContextWrapper[Any],
        from_agent: Agent[Any],
        to_agent: Agent[Any],
    ) -> None:
        del context
        self._handoff_index += 1
        from_name = from_agent.name
        to_name = to_agent.name
        from_run_agent_id = self._resolve_run_agent_id(from_name)
        to_run_agent_id = self._resolve_run_agent_id(to_name)

        note_data = pending_handoff_note.get()
        handoff_note_json = json.dumps(note_data, ensure_ascii=False, separators=(",", ":")) if note_data else None

        self._observer.emit(
            AgentHandoff(
                record=AgentHandoffRecord(
                    handoff_id=make_handoff_id(self._run_id, self._iteration_index, self._handoff_index),
                    run_id=self._run_id,
                    iteration_id=self._iteration_id,
                    from_agent_name=from_name,
                    to_agent_name=to_name,
                    from_run_agent_id=from_run_agent_id,
                    to_run_agent_id=to_run_agent_id,
                    occurred_at=utc_now_iso(),
                    handoff_note_json=handoff_note_json,
                )
            )
        )
        self._current_agent_name = to_name
        pending_handoff_note.set(None)

    async def on_tool_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Any,
    ) -> None:
        if agent is not None and hasattr(agent, "name"):
            self._current_agent_name = agent.name
        self._seq += 1
        tool_name_str = str(getattr(tool, "name", None) or tool.__class__.__name__)
        count = self._tool_start_count.get(tool_name_str, 0)
        self._tool_start_count[tool_name_str] = count + 1
        self._pending_starts.setdefault(tool_name_str, []).append(
            (self._seq, utc_now_iso(), count)
        )

    async def on_tool_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Any,
        result: str,
    ) -> None:
        tool_name = getattr(tool, "name", None) or tool.__class__.__name__
        tool_name_str = str(tool_name)
        agent_name = agent.name if hasattr(agent, "name") else self._current_agent_name

        # Pop the matching start entry (FIFO — first started, first ended).
        stack = self._pending_starts.get(tool_name_str, [])
        if stack:
            seq, started_at, retry_idx = stack.pop(0)
        else:
            seq = self._seq
            started_at = None
            retry_idx = None

        finished_at = utc_now_iso()
        duration_seconds = None
        if started_at:
            try:
                start_dt = datetime.fromisoformat(started_at)
                finished_dt = datetime.fromisoformat(finished_at)
                duration_seconds = (finished_dt - start_dt).total_seconds()
            except (ValueError, TypeError):
                pass

        run_agent_id = self._resolve_run_agent_id(agent_name) if agent_name else None

        # Prefer registered ToolDescriptor; fall back to legacy summarizers.
        _descriptor = _get_descriptor(tool_name_str)
        if _descriptor is not None:
            result_summary = _descriptor.summarize_result(result)
            ts, success = _descriptor.classify_status(result)
            status = ts.value
        else:
            result_summary = summarize_tool_result(tool_name, result)
            ts, success = classify_json_envelope(result)
            status = ts.value
        result_summary_json = json.dumps(result_summary, ensure_ascii=False, separators=(",", ":"))

        error_type, error_message_short = _error_info(result, success)

        args_summary_json = None
        raw_args = getattr(context, "tool_arguments", None)
        if raw_args is not None:
            try:
                tool_args = json.loads(raw_args)
                if _descriptor is not None:
                    args_summary = _descriptor.summarize_args(tool_args)
                else:
                    args_summary = summarize_tool_args(tool_name, tool_args)
                args_summary_json = json.dumps(args_summary, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                pass
        del context

        self._observer.emit(
            ToolCalled(
                record=ToolCallRecord(
                    tool_call_id=f"tc-{uuid.uuid4().hex[:12]}",
                    run_id=self._run_id,
                    iteration_id=self._iteration_id,
                    agent_execution_id=self._agent_execution_id,
                    seq=seq,
                    tool_name=tool_name_str,
                    status=status,
                    success=success,
                    agent_name=agent_name,
                    run_agent_id=run_agent_id,
                    started_at=started_at,
                    finished_at=finished_at,
                    duration_seconds=duration_seconds,
                    args_summary_json=args_summary_json,
                    result_summary_json=result_summary_json,
                    retry_index=retry_idx,
                    error_type=error_type,
                    error_message_short=error_message_short,
                )
            )
        )
        # Live context accumulation for rate-limit retry recovery
        _retry_args: dict[str, Any] = {}
        if raw_args is not None:
            try:
                parsed = json.loads(raw_args)
                if isinstance(parsed, dict):
                    _retry_args = parsed
            except Exception:  # noqa: BLE001
                pass
        self._accumulate_retry_context(tool_name_str, _retry_args, result)

    def _accumulate_retry_context(self, tool_name: str, args: dict[str, Any], result: str) -> None:
        """Accumulate research context for use when recovering from a rate-limit retry."""
        try:
            if tool_name == "search_files":
                data = json.loads(result)
                for r in (data.get("results") or []):
                    path = r.get("path", "")
                    if not path or path.startswith(("test/", "tests/", "test\\", "tests\\")):
                        continue
                    line = r.get("line", "")
                    match_text = str(r.get("match", ""))[:80]
                    if len(self._retry_searches) < 5:
                        self._retry_searches.append(f"{path}:{line} → {match_text}")
            elif tool_name == "read_file":
                path = args.get("path", "")
                if path:
                    start = args.get("start_line")
                    end = args.get("end_line")
                    loc = f":{start}-{end}" if start else ""
                    entry = f"{path}{loc}"
                    if entry not in self._retry_files_read:
                        self._retry_files_read.append(entry)
            elif tool_name in ("replace_in_file", "replace_lines", "write_file"):
                path = args.get("path", "")
                if path:
                    try:
                        data = json.loads(result)
                        ok = data.get("ok", False)
                        error = data.get("error", "")
                        edit_status = "ok" if ok else f"failed:{error}"
                    except Exception:  # noqa: BLE001
                        edit_status = "?"
                    self._retry_edit_attempts.append(f"{tool_name}({path}) → {edit_status}")
        except Exception:  # noqa: BLE001
            pass

    def extract_context_snapshot(self) -> str | None:
        """Return a summary of accumulated research context for rate-limit retry recovery."""
        parts: list[str] = []
        if self._retry_searches:
            parts.append("Search hits:")
            parts.extend(f"  {hit}" for hit in self._retry_searches)
        if self._retry_files_read:
            unique = list(dict.fromkeys(self._retry_files_read))[-5:]
            parts.append(f"Files read: {', '.join(unique)}")
        if self._retry_edit_attempts:
            parts.append(f"Edit attempts: {', '.join(self._retry_edit_attempts)}")
        return "\n".join(parts) if parts else None

    def reset_context_snapshot(self) -> None:
        """Reset accumulated context before each retry attempt."""
        self._retry_searches = []
        self._retry_files_read = []
        self._retry_edit_attempts = []
