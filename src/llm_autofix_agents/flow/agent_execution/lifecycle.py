from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.observability import AgentExecutionRecord, RunObserver, utc_now_iso


@dataclass(frozen=True)
class AgentExecutionLifecycle:
    """Encapsulates agent-execution observability lifecycle."""

    def start(
        self,
        *,
        observer: RunObserver,
        agent_execution_id: str,
        run_id: str,
        iteration_id: str,
        run_agent_id: str,
    ) -> str:
        started_at = utc_now_iso()
        observer.on_agent_execution_started(
            record=AgentExecutionRecord.started(
                agent_execution_id=agent_execution_id,
                run_id=run_id,
                iteration_id=iteration_id,
                run_agent_id=run_agent_id,
            )
        )
        return started_at

    def finish(
        self,
        *,
        observer: RunObserver,
        agent_execution_id: str,
        run_id: str,
        iteration_id: str,
        run_agent_id: str,
        started_at: str,
        status: str,
        reasoning_summary: str,
        confidence: float,
        notes: str | None,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        tool_calls_count: int,
    ) -> None:
        observer.on_agent_execution_finished(
            record=AgentExecutionRecord.finished(
                agent_execution_id=agent_execution_id,
                run_id=run_id,
                iteration_id=iteration_id,
                run_agent_id=run_agent_id,
                execution_index=1,
                started_at=started_at,
                status=status,
                reasoning_summary=reasoning_summary,
                confidence=confidence,
                notes=notes,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                tool_calls_count=tool_calls_count,
            )
        )
