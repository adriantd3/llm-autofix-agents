from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass

from llm_autofix_agents.flow.errors import ProviderExecutionError
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.llm.provider_events import ProviderCallEvent
from llm_autofix_agents.observability.telemetry import IterationTelemetry
from llm_autofix_agents.tools.context import APRToolContext


@dataclass(frozen=True)
class AgentExecutionContext:
    run_agent_id: str
    run_agent_ids: dict[str, str]
    agent_context: APRToolContext
    iteration_telemetry: IterationTelemetry
    user_input: str
    max_turns: int


@dataclass(frozen=True)
class AgentExecutionResult:
    proposal: AgentFixIterationRecord
    agent_execution_id: str
    tool_calls_count: int


@dataclass(frozen=True)
class AgentExecutionRunner:
    """Reusable single-agent execution lifecycle runner."""

    def invoke_agent(
        self,
        *,
        context: AgentExecutionContext,
        execution_index: int,
        provider_call: Callable[
            [object, Callable[[ProviderCallEvent], None] | None],
            Coroutine[object, object, AgentFixIterationRecord],
        ],
    ) -> AgentExecutionResult:
        agent_telemetry = context.iteration_telemetry.start_agent_execution(
            run_agent_id=context.run_agent_id,
            execution_index=execution_index,
        )
        hooks = agent_telemetry.create_hooks(run_agent_ids=context.run_agent_ids)

        started_monotonic = time.perf_counter()

        try:
            proposal = _run_sync(provider_call(hooks, agent_telemetry.handle_provider_call_event))
        except Exception as exc:  # noqa: BLE001
            duration_seconds = time.perf_counter() - started_monotonic
            agent_telemetry.finish_failed(
                error=exc, tool_calls_count=hooks.tool_call_count, duration_seconds=duration_seconds
            )
            raise ProviderExecutionError(f"provider execution failed: {exc}") from exc

        duration_seconds = time.perf_counter() - started_monotonic
        agent_telemetry.finish(
            proposal=proposal, tool_calls_count=hooks.tool_call_count, duration_seconds=duration_seconds
        )
        return AgentExecutionResult(
            proposal=proposal,
            agent_execution_id=agent_telemetry.agent_execution_id,
            tool_calls_count=hooks.tool_call_count,
        )


def _run_sync(awaitable: Coroutine[object, object, AgentFixIterationRecord]) -> AgentFixIterationRecord:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("Cannot be called from an active event loop")
