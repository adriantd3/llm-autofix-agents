"""Emitter — single high-level API replacing the 3-tier RunTelemetry/IterationTelemetry/AgentExecutionTelemetry.

Callers translate domain objects (AgentFixIterationRecord, ProviderCallEvent) to
plain primitives *before* calling Emitter methods; the observability layer does
not import from llm.provider.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from hashlib import sha256
from typing import TYPE_CHECKING, Protocol

from llm_autofix_agents.observability.events import (
    AgentExecutionFinished,
    AgentExecutionStarted,
    AgentHandoff,
    AgentRegistered,
    FacadeInput,
    FileChanged,
    IterationFinished,
    IterationStarted,
    ObservabilityEvent,
    ProviderCallHappened,
    RunFinished,
    RunStarted,
    TestExecuted,
    ToolCalled,
)
from llm_autofix_agents.observability.models import (
    AgentDescriptor,
    AgentExecutionRecord,
    AgentHandoffRecord,
    FacadeInputRecord,
    FileChangeRecord,
    IterationRecord,
    ModelConfigDescriptor,
    ProviderCallRecord,
    RunDescriptor,
    RunFinishedRecord,
    TestExecutionRecord,
    ToolCallRecord,
    make_file_change_id,
    make_handoff_id,
    make_test_execution_id,
    utc_now_iso,
)

if TYPE_CHECKING:
    pass


def _stable_id(prefix: str, payload: str) -> str:
    digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


class Observer(Protocol):
    def emit(self, event: ObservabilityEvent) -> None: ...


@dataclass(frozen=True)
class IterationContext:
    """Value object carrying iteration-level identifiers for Emitter methods."""

    iteration_id: str
    iteration_index: int


class Emitter:
    """Single observability API for an APR run.

    Replaces RunTelemetry → IterationTelemetry → AgentExecutionTelemetry chain.
    Does NOT import from llm.provider; callers translate domain objects at the seam.
    """

    def __init__(self, *, observer: Observer, run_id: str) -> None:
        self._observer = observer
        self._run_id = run_id

    @property
    def run_id(self) -> str:
        return self._run_id

    # ── Run lifecycle ─────────────────────────────────────────────────────

    def start_run(
        self,
        *,
        architecture: str,
        target_repo: str | None,
        target_branch: str | None,
        run_fingerprint: str,
        prompt: str,
        benchmark_name: str | None,
        problem_id: str | None,
    ) -> None:
        self._observer.emit(
            RunStarted(
                run=RunDescriptor(
                    run_id=self._run_id,
                    architecture=architecture,
                    target_repo=target_repo,
                    target_branch=target_branch,
                    run_fingerprint=run_fingerprint,
                    prompt_hash=sha256(prompt.encode("utf-8")).hexdigest()[:16],
                    benchmark_name=benchmark_name,
                    problem_id=problem_id,
                ),
                started_at=utc_now_iso(),
            )
        )

    def register_agent(
        self,
        *,
        agent_name: str,
        agent_role: str,
        provider: str,
        model: str,
        max_turns: int,
        tool_profile: str,
        instructions: str,
        base_url: str | None,
        tracing_disabled: bool,
        agent_order: int = 1,
    ) -> str:
        payload = f"{self._run_id}|{agent_name}|{agent_role}|{agent_order}"
        run_agent_id = _stable_id("ra", payload)
        self._observer.emit(
            AgentRegistered(
                run_id=self._run_id,
                run_agent_id=run_agent_id,
                agent=AgentDescriptor(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    model_config=ModelConfigDescriptor(
                        provider=provider,
                        model=model,
                        max_turns=max_turns,
                        base_url=base_url,
                        tracing_disabled=tracing_disabled,
                    ),
                    tool_profile=tool_profile,
                    agent_order=agent_order,
                ),
                instructions_hash=sha256(instructions.encode("utf-8")).hexdigest()[:16],
            )
        )
        return run_agent_id or f"{self._run_id}-agent-{agent_name}"

    def finish_run(
        self,
        *,
        final_status: str,
        stop_reason: str,
        duration_seconds: float,
        total_iterations: int,
        total_input_tokens: int,
        total_output_tokens: int,
        total_tokens: int,
        files_changed_count: int,
        resolved: bool,
        live_log_path: str | None,
        summary_path: str | None,
    ) -> None:
        self._observer.emit(
            RunFinished(
                run_finished=RunFinishedRecord(
                    run_id=self._run_id,
                    finished_at=utc_now_iso(),
                    final_status=final_status,
                    stop_reason=stop_reason,
                    duration_seconds=duration_seconds,
                    total_iterations=total_iterations,
                    total_input_tokens=total_input_tokens,
                    total_output_tokens=total_output_tokens,
                    total_tokens=total_tokens,
                    files_changed_count=files_changed_count,
                    resolved=resolved,
                    live_log_path=live_log_path,
                    summary_path=summary_path,
                )
            )
        )

    def record_test_execution(
        self,
        ctx: IterationContext | None,
        *,
        phase: str,
        command: str | None,
        exit_code: int,
        timed_out: bool,
        signature: str,
        iteration: int = 0,
        agent_execution_id: str | None = None,
    ) -> None:
        iteration_idx = ctx.iteration_index if ctx is not None else iteration
        iteration_id = ctx.iteration_id if ctx is not None else None
        self._observer.emit(
            TestExecuted(
                record=TestExecutionRecord.create(
                    test_execution_id=make_test_execution_id(self._run_id, iteration_idx),
                    run_id=self._run_id,
                    phase=phase,
                    command=command,
                    exit_code=exit_code,
                    timed_out=timed_out,
                    signature=signature,
                    iteration_id=iteration_id,
                    agent_execution_id=agent_execution_id,
                )
            )
        )

    # ── Iteration lifecycle ───────────────────────────────────────────────

    def start_iteration(self, *, iteration_id: str, iteration_index: int) -> IterationContext:
        self._observer.emit(
            IterationStarted(
                record=IterationRecord.started(
                    run_id=self._run_id,
                    iteration_id=iteration_id,
                    iteration_index=iteration_index,
                )
            )
        )
        return IterationContext(iteration_id=iteration_id, iteration_index=iteration_index)

    def finish_iteration(
        self,
        ctx: IterationContext,
        *,
        started_at: str,
        status: str | None = None,
        stop_reason: str | None = None,
        duration_seconds: float | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        tool_calls_count: int = 0,
        changed_files_count: int = 0,
        repo_changed: bool = False,
        test_exit_code: int | None = None,
        test_timed_out: bool | None = None,
        test_signature: str | None = None,
    ) -> None:
        self._observer.emit(
            IterationFinished(
                record=IterationRecord.finished(
                    run_id=self._run_id,
                    iteration_id=ctx.iteration_id,
                    iteration_index=ctx.iteration_index,
                    started_at=started_at,
                    status=status,
                    stop_reason=stop_reason,
                    duration_seconds=duration_seconds,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    tool_calls_count=tool_calls_count,
                    changed_files_count=changed_files_count,
                    repo_changed=repo_changed,
                    test_exit_code=test_exit_code,
                    test_timed_out=test_timed_out,
                    test_signature=test_signature,
                )
            )
        )

    def record_facade_input(self, ctx: IterationContext, input_text: str) -> None:
        self._observer.emit(
            FacadeInput(
                record=FacadeInputRecord(
                    run_id=self._run_id,
                    iteration_id=ctx.iteration_id,
                    iteration_index=ctx.iteration_index,
                    input_text=input_text,
                    occurred_at=utc_now_iso(),
                )
            )
        )

    def record_file_changes(
        self,
        ctx: IterationContext,
        *,
        agent_execution_id: str,
        modified: list[str],
        added: list[str],
        deleted: list[str],
        untracked: list[str],
    ) -> None:
        entries = (
            [(p, "modified") for p in modified]
            + [(p, "added") for p in added]
            + [(p, "deleted") for p in deleted]
            + [(p, "untracked") for p in untracked]
        )
        for index, (path, change_type) in enumerate(entries, start=1):
            self._observer.emit(
                FileChanged(
                    record=FileChangeRecord.create(
                        file_change_id=make_file_change_id(self._run_id, ctx.iteration_index, index),
                        run_id=self._run_id,
                        path=path,
                        change_type=change_type,
                        detected_by="workspace_snapshot",
                        iteration_id=ctx.iteration_id,
                        agent_execution_id=agent_execution_id,
                    )
                )
            )

    # ── Agent execution lifecycle ─────────────────────────────────────────

    def start_agent_execution(
        self,
        ctx: IterationContext,
        *,
        run_agent_id: str,
        execution_index: int,
        run_agent_ids: dict[str, str] | None = None,
    ) -> tuple[str, object]:
        """Start an agent execution; returns (agent_execution_id, APRRunHooks)."""
        from llm_autofix_agents.observability.lifecycle_hooks import APRRunHooks

        agent_execution_id = f"{self._run_id}-it{ctx.iteration_index:02d}-agent{execution_index:02d}"
        self._observer.emit(
            AgentExecutionStarted(
                record=AgentExecutionRecord.started(
                    agent_execution_id=agent_execution_id,
                    run_id=self._run_id,
                    iteration_id=ctx.iteration_id,
                    run_agent_id=run_agent_id,
                    execution_index=execution_index,
                )
            )
        )
        hooks = APRRunHooks(
            observer=self._observer,
            run_id=self._run_id,
            iteration_id=ctx.iteration_id,
            agent_execution_id=agent_execution_id,
            run_agent_ids=run_agent_ids,
            iteration_index=ctx.iteration_index,
        )
        return agent_execution_id, hooks

    def finish_agent_execution(
        self,
        ctx: IterationContext,
        *,
        agent_execution_id: str,
        started_at: str,
        run_agent_id: str,
        execution_index: int,
        status: str = "unknown",
        reasoning_summary: str = "",
        confidence: float = 0.0,
        notes: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
        tool_calls_count: int = 0,
        duration_seconds: float = 0.0,
        error_type: str | None = None,
        error_message_short: str | None = None,
    ) -> None:
        self._observer.emit(
            AgentExecutionFinished(
                record=AgentExecutionRecord.finished(
                    agent_execution_id=agent_execution_id,
                    run_id=self._run_id,
                    iteration_id=ctx.iteration_id,
                    run_agent_id=run_agent_id,
                    execution_index=execution_index,
                    started_at=started_at,
                    status=status,
                    reasoning_summary=reasoning_summary,
                    confidence=confidence,
                    notes=notes,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    total_tokens=total_tokens,
                    tool_calls_count=tool_calls_count,
                    error_type=error_type,
                    error_message_short=error_message_short,
                    duration_seconds=duration_seconds,
                )
            )
        )

    def emit_provider_call(self, record: ProviderCallRecord) -> None:
        self._observer.emit(ProviderCallHappened(record=record))

    def emit_tool_call(self, record: ToolCallRecord) -> None:
        self._observer.emit(ToolCalled(record=record))

    def emit_agent_handoff(self, *, ctx: IterationContext, handoff_index: int, record: AgentHandoffRecord) -> None:
        self._observer.emit(AgentHandoff(record=record))

    def emit_raw(self, event: ObservabilityEvent) -> None:
        """Direct emit for hooks that already have the full event."""
        self._observer.emit(event)
