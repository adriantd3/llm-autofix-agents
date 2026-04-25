from __future__ import annotations

import asyncio
import time
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field

from llm_autofix_agents.flow.architecture import AgentIterationContext
from llm_autofix_agents.flow.errors import ProviderExecutionError
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.observability import APRRunHooks

from .lifecycle import AgentExecutionLifecycle


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

    lifecycle: AgentExecutionLifecycle = field(default_factory=AgentExecutionLifecycle)

    def run_agent(
        self,
        *,
        context: AgentIterationContext,
        execution_index: int,
        provider_call: Callable[[APRRunHooks], Coroutine[object, object, AgentFixIterationRecord]],
    ) -> AgentExecutionResult:
        agent_execution_id = f"{context.run_id}-it{context.iteration_index:02d}-agent{execution_index:02d}"
        hooks = APRRunHooks(
            observer=context.observer,
            run_id=context.run_id,
            iteration_id=context.iteration_id,
            agent_execution_id=agent_execution_id,
        )

        started_monotonic = time.perf_counter()
        started_at = self.lifecycle.start(
            observer=context.observer,
            agent_execution_id=agent_execution_id,
            run_id=context.run_id,
            iteration_id=context.iteration_id,
            run_agent_id=context.run_agent_id,
        )

        try:
            proposal = _run_sync(provider_call(hooks))
        except Exception as exc:  # noqa: BLE001
            raise ProviderExecutionError(f"provider execution failed: {exc}") from exc

        self.lifecycle.finish(
            observer=context.observer,
            agent_execution_id=agent_execution_id,
            run_id=context.run_id,
            iteration_id=context.iteration_id,
            run_agent_id=context.run_agent_id,
            started_at=started_at,
            status=proposal.status,
            reasoning_summary=proposal.reasoning_summary,
            confidence=proposal.confidence,
            notes=proposal.notes,
            input_tokens=proposal.input_tokens,
            output_tokens=proposal.output_tokens,
            total_tokens=proposal.total_tokens,
            tool_calls_count=hooks.tool_call_count,
        )
        return AgentExecutionResult(
            proposal=proposal,
            agent_execution_id=agent_execution_id,
            started_at=started_at,
            duration_seconds=max(0.0, time.perf_counter() - started_monotonic),
            tool_calls_count=hooks.tool_call_count,
        )


def _run_sync(awaitable: Coroutine[object, object, AgentFixIterationRecord]) -> AgentFixIterationRecord:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("Cannot be called from an active event loop")
