from __future__ import annotations

import json
from typing import Any

from agents import Agent, RunContextWrapper, RunHooks

from llm_autofix_agents.observability.models import ToolCallRecord
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
    ) -> None:
        self._observer = observer
        self._run_id = run_id
        self._iteration_id = iteration_id
        self._agent_execution_id = agent_execution_id
        self._seq = 0

    @property
    def tool_call_count(self) -> int:
        return self._seq

    async def on_tool_start(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Any,
    ) -> None:
        del context, agent, tool
        self._seq += 1

    async def on_tool_end(
        self,
        context: RunContextWrapper[Any],
        agent: Agent[Any],
        tool: Any,
        result: str,
    ) -> None:
        del context, agent
        tool_name = getattr(tool, "name", None) or tool.__class__.__name__
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
            )
        )
