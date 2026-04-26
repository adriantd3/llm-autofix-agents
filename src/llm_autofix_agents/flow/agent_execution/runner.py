from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass

from llm_autofix_agents.flow.architecture import AgentIterationContext
from llm_autofix_agents.flow.errors import ProviderExecutionError
from llm_autofix_agents.llm.provider import AgentFixIterationRecord


@dataclass(frozen=True)
class AgentExecutionResult:
    proposal: AgentFixIterationRecord
    agent_execution_id: str
    started_at: str
    duration_seconds: float
    tool_calls_count: int


@dataclass(frozen=True)
class AgentExecutionRunner:
    """Reusable single-agent execution lifecycle runner."""

    def run_agent(
        self,
        *,
        context: AgentIterationContext,
        execution_index: int,
        provider_call: Callable[[object], Coroutine[object, object, AgentFixIterationRecord]],
    ) -> AgentExecutionResult:
        agent_telemetry = context.iteration_telemetry.start_agent_execution(
            run_agent_id=context.run_agent_id,
            execution_index=execution_index,
        )
        hooks = agent_telemetry.create_hooks()

        started_monotonic = time.perf_counter()

        try:
            proposal = _run_sync(provider_call(hooks))
        except Exception as exc:  # noqa: BLE001
            agent_telemetry.finish_failed(error=exc, tool_calls_count=hooks.tool_call_count)
            raise ProviderExecutionError(f"provider execution failed: {exc}") from exc

        agent_telemetry.finish(proposal=proposal, tool_calls_count=hooks.tool_call_count)
        return AgentExecutionResult(
            proposal=proposal,
            agent_execution_id=agent_telemetry.agent_execution_id,
            started_at=agent_telemetry.started_at,
            duration_seconds=max(0.0, time.perf_counter() - started_monotonic),
            tool_calls_count=hooks.tool_call_count,
        )


def _run_sync(awaitable: Coroutine[object, object, AgentFixIterationRecord]) -> AgentFixIterationRecord:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("Cannot be called from an active event loop")
