from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

from llm_autofix_agents.flow import AgentIterationContext, AgentIterationResult
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.observability import AgentExecutionRecord, APRRunHooks, utc_now_iso


@dataclass(frozen=True)
class MonoAgentArchitecture:
    """Baseline architecture: one autonomous fixer agent per iteration."""

    instructions: str
    architecture_name: str = "mono_agent"
    agent_name: str = "baseline"
    agent_role: str = "fixer"

    def run_iteration(self, context: AgentIterationContext) -> AgentIterationResult:
        agent_execution_id = f"{context.run_id}-it{context.iteration_index:02d}-agent01"
        hooks = APRRunHooks(
            observer=context.observer,
            run_id=context.run_id,
            iteration_id=context.iteration_id,
            agent_execution_id=agent_execution_id,
        )

        started_at = utc_now_iso()
        started_monotonic = time.perf_counter()

        context.observer.on_agent_execution_started(
            record=AgentExecutionRecord.started(
                agent_execution_id=agent_execution_id,
                run_id=context.run_id,
                iteration_id=context.iteration_id,
                run_agent_id=context.run_agent_id,
            )
        )

        proposal = _run_sync(
            context.provider.run_prompt(
                instructions=self.instructions,
                user_input=context.user_input,
                max_turns=context.max_turns,
                tools=context.agent_tools,
                context=context.agent_context,
                hooks=hooks,
            )
        )

        duration_seconds = max(0.0, time.perf_counter() - started_monotonic)

        context.observer.on_agent_execution_finished(
            record=AgentExecutionRecord.finished(
                agent_execution_id=agent_execution_id,
                run_id=context.run_id,
                iteration_id=context.iteration_id,
                run_agent_id=context.run_agent_id,
                execution_index=1,
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
        )

        return AgentIterationResult(
            proposal=proposal,
            agent_execution_id=agent_execution_id,
            started_at=started_at,
            duration_seconds=duration_seconds,
            tool_calls_count=hooks.tool_call_count,
        )


def _run_sync(awaitable: Coroutine[object, object, AgentFixIterationRecord]) -> AgentFixIterationRecord:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("Cannot be called from an active event loop")
