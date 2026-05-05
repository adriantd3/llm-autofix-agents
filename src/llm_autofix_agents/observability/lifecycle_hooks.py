from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from agents import Agent, RunContextWrapper, RunHooks

from llm_autofix_agents.observability.models import AgentHandoffRecord, ToolCallRecord, make_handoff_id, utc_now_iso
from llm_autofix_agents.observability.observer import RunObserver
from llm_autofix_agents.observability.tool_context import pending_handoff_note
from llm_autofix_agents.observability.tool_summaries import summarize_tool_args, summarize_tool_result


def infer_tool_status(result: str) -> tuple[str, bool | None]:
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return "unknown", None

    if not isinstance(payload, dict):
        return "unknown", None

    ok = payload.get("ok")
    if ok is True:
        return "success", True
    if ok is False:
        return "failed", False
    return "unknown", None


def _result_excerpt(result: str, max_len: int = 200) -> str:
    if len(result) <= max_len:
        return result
    return result[:max_len] + "..."


def _error_info(result: str, status: str, success: bool | None) -> tuple[str | None, str | None]:
    if success is not False:
        return None, None
    try:
        payload = json.loads(result)
        if isinstance(payload, dict):
            error = payload.get("error")
            if error is not None:
                error_type = type(error).__name__ if not isinstance(error, str) else "tool_error"
                error_message = str(error)[:500]
                return error_type, error_message
    except json.JSONDecodeError:
        pass
    return "tool_error", result[:500]


class APRRunHooks(RunHooks[Any]):
    def __init__(
        self,
        *,
        observer: RunObserver,
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
        self._tool_started_at: dict[int, str] = {}

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

        self._observer.on_agent_handoff(
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
        self._tool_started_at[self._seq] = utc_now_iso()

    async def on_tool_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Any,
        result: str,
    ) -> None:
        tool_name = getattr(tool, "name", None) or tool.__class__.__name__
        agent_name = agent.name if hasattr(agent, "name") else self._current_agent_name
        status, success = infer_tool_status(result)

        finished_at = utc_now_iso()
        started_at = self._tool_started_at.pop(self._seq, None)
        duration_seconds = None
        if started_at:
            try:
                start_dt = datetime.fromisoformat(started_at)
                finished_dt = datetime.fromisoformat(finished_at)
                duration_seconds = (finished_dt - start_dt).total_seconds()
            except (ValueError, TypeError):
                pass

        run_agent_id = self._resolve_run_agent_id(agent_name) if agent_name else None

        result_summary = summarize_tool_result(tool_name, result)
        result_summary_json = json.dumps(result_summary, ensure_ascii=False, separators=(",", ":"))
        result_excerpt_val = _result_excerpt(result)

        error_type, error_message_short = _error_info(result, status, success)

        args_summary_json = None
        raw_args = getattr(context, "tool_arguments", None)
        if raw_args is not None:
            try:
                tool_args = json.loads(raw_args)
                args_summary = summarize_tool_args(tool_name, tool_args)
                args_summary_json = json.dumps(args_summary, ensure_ascii=False, separators=(",", ":"))
            except Exception:
                pass
        del context

        self._observer.on_tool_call(
            record=ToolCallRecord(
                tool_call_id=f"tc-{uuid.uuid4().hex[:12]}",
                run_id=self._run_id,
                iteration_id=self._iteration_id,
                agent_execution_id=self._agent_execution_id,
                seq=self._seq,
                tool_name=str(tool_name),
                status=status,
                success=success,
                agent_name=agent_name,
                run_agent_id=run_agent_id,
                started_at=started_at,
                finished_at=finished_at,
                duration_seconds=duration_seconds,
                args_summary_json=args_summary_json,
                result_summary_json=result_summary_json,
                result_excerpt=result_excerpt_val,
                error_type=error_type,
                error_message_short=error_message_short,
            )
        )
