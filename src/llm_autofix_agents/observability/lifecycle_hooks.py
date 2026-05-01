from __future__ import annotations

import json
from typing import Any

from agents import Agent, RunContextWrapper, RunHooks

from llm_autofix_agents.observability.models import AgentHandoffRecord, ToolCallRecord, make_handoff_id, utc_now_iso
from llm_autofix_agents.observability.observer import RunObserver


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
            )
        )
        self._current_agent_name = to_name

    async def on_tool_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Any,
    ) -> None:
        del context, tool
        if agent is not None and hasattr(agent, "name"):
            self._current_agent_name = agent.name
        self._seq += 1

    async def on_tool_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Any,
        result: str,
    ) -> None:
        del context
        tool_name = getattr(tool, "name", None) or tool.__class__.__name__
        agent_name = agent.name if hasattr(agent, "name") else self._current_agent_name
        status, success = infer_tool_status(result)
        self._observer.on_tool_call(
            record=ToolCallRecord(
                tool_call_id=f"{self._agent_execution_id}-tool{self._seq:03d}",
                run_id=self._run_id,
                iteration_id=self._iteration_id,
                agent_execution_id=self._agent_execution_id,
                seq=self._seq,
                tool_name=str(tool_name),
                status=status,
                success=success,
                agent_name=agent_name,
            )
        )
