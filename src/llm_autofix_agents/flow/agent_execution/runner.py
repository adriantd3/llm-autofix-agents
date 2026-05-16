from __future__ import annotations

import asyncio
import time
from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any

from llm_autofix_agents.flow.errors import ProviderExecutionError
from llm_autofix_agents.llm.provider import AgentFixIterationRecord, LLMProvider
from llm_autofix_agents.observability.emitter import Emitter, IterationContext
from llm_autofix_agents.tools.context import APRToolContext


@dataclass(frozen=True)
class AgentExecutionContext:
    run_agent_id: str
    run_agent_ids: dict[str, str]
    agent_context: APRToolContext
    emitter: Emitter
    iteration_ctx: IterationContext
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
        provider: LLMProvider,
        agent: Any,
    ) -> AgentExecutionResult:
        emitter = context.emitter
        ctx = context.iteration_ctx

        agent_execution_id, hooks = emitter.start_agent_execution(
            ctx,
            run_agent_id=context.run_agent_id,
            execution_index=execution_index,
            run_agent_ids=context.run_agent_ids,
        )
        from llm_autofix_agents.observability.models import utc_now_iso
        started_at = utc_now_iso()
        started_monotonic = time.perf_counter()

        # Translate ProviderCallEvent → ProviderCallRecord at the seam (flow knows llm.provider).
        from llm_autofix_agents.llm.provider_events import ProviderCallEvent
        from llm_autofix_agents.observability.models import ProviderCallRecord

        def _provider_callback(raw_event: object) -> None:
            if not isinstance(raw_event, ProviderCallEvent):
                return
            event = raw_event
            emitter.emit_provider_call(
                ProviderCallRecord(
                    provider_call_id=f"{agent_execution_id}-{event.event_type}-{event.attempt:02d}",
                    run_id=emitter.run_id,
                    iteration_id=ctx.iteration_id,
                    agent_execution_id=agent_execution_id,
                    event_type=event.event_type,
                    attempt=event.attempt,
                    total_attempts=event.total_attempts,
                    status_code=event.status_code,
                    error_type=event.error_type,
                    error_message_short=event.error_message_short,
                    tool_calls_count=event.tool_calls_count,
                    retry_delay_seconds=event.retry_delay_seconds,
                    rerun_full_runner=event.rerun_full_runner,
                    occurred_at=utc_now_iso(),
                )
            )

        try:
            proposal = _run_sync(
                provider.run_agent(
                    agent=agent,
                    user_input=context.user_input,
                    max_turns=context.max_turns,
                    context=context.agent_context,
                    hooks=hooks,
                    event_callback=_provider_callback,
                )
            )
        except Exception as exc:  # noqa: BLE001
            duration_seconds = time.perf_counter() - started_monotonic
            message = str(exc).strip() or exc.__class__.__name__
            emitter.finish_agent_execution(
                ctx,
                agent_execution_id=agent_execution_id,
                started_at=started_at,
                run_agent_id=context.run_agent_id,
                execution_index=execution_index,
                status="failed",
                error_type=exc.__class__.__name__,
                error_message_short=message[:500],
                tool_calls_count=hooks.tool_call_count,
                duration_seconds=duration_seconds,
            )
            raise ProviderExecutionError(f"provider execution failed: {exc}") from exc

        duration_seconds = time.perf_counter() - started_monotonic

        p = proposal.proposal if isinstance(proposal, AgentFixIterationRecord) else None
        emitter.finish_agent_execution(
            ctx,
            agent_execution_id=agent_execution_id,
            started_at=started_at,
            run_agent_id=context.run_agent_id,
            execution_index=execution_index,
            status=p.status if p else "unknown",
            reasoning_summary=p.reasoning_summary if p else "",
            confidence=p.confidence if p else 0.0,
            notes=p.notes if p else None,
            input_tokens=proposal.input_tokens if isinstance(proposal, AgentFixIterationRecord) else 0,
            output_tokens=proposal.output_tokens if isinstance(proposal, AgentFixIterationRecord) else 0,
            total_tokens=proposal.total_tokens if isinstance(proposal, AgentFixIterationRecord) else 0,
            tool_calls_count=hooks.tool_call_count,
            duration_seconds=duration_seconds,
        )
        return AgentExecutionResult(
            proposal=proposal,
            agent_execution_id=agent_execution_id,
            tool_calls_count=hooks.tool_call_count,
        )


def _run_sync(awaitable: Coroutine[object, object, AgentFixIterationRecord]) -> AgentFixIterationRecord:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("Cannot be called from an active event loop")
