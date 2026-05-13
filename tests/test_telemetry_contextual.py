"""Tests for the Emitter API (replaces RunTelemetry/IterationTelemetry/AgentExecutionTelemetry)."""
from __future__ import annotations

from typing import Any

from llm_autofix_agents.flow.models import WorkspaceChangeSet
from llm_autofix_agents.observability.emitter import Emitter, IterationContext
from llm_autofix_agents.observability.events import (
    AgentExecutionFinished,
    AgentExecutionStarted,
    AgentHandoff,
    FacadeInput,
    FileChanged,
    IterationFinished,
    IterationStarted,
    ObservabilityEvent,
    ProviderCallHappened,
    TestExecuted,
    ToolCalled,
)
from llm_autofix_agents.observability.observer import NullObserver


class _CaptureObserver:
    def __init__(self) -> None:
        self.events: list[ObservabilityEvent] = []

    def emit(self, event: ObservabilityEvent) -> None:
        self.events.append(event)

    def events_of(self, event_type: type) -> list[Any]:
        return [e for e in self.events if isinstance(e, event_type)]


def _make_emitter() -> tuple[Emitter, _CaptureObserver]:
    observer = _CaptureObserver()
    return Emitter(observer=observer, run_id="run-1"), observer


def test_file_change_emitter_records_correct_types() -> None:
    emitter, observer = _make_emitter()
    ctx = IterationContext(iteration_id="it-1", iteration_index=1)

    changes = WorkspaceChangeSet(
        modified_files=["a.py", "b.py"],
        added_files=["c.py"],
        deleted_files=["d.py"],
        untracked_files=["e.py"],
        diff="",
        diff_excludes_untracked=False,
    )
    emitter.record_file_changes(
        ctx,
        agent_execution_id="agent-1",
        modified=list(changes.modified_files),
        added=list(changes.added_files),
        deleted=list(changes.deleted_files),
        untracked=list(changes.untracked_files),
    )

    file_events = observer.events_of(FileChanged)
    types_by_path = {e.record.path: e.record.change_type for e in file_events}
    assert types_by_path["a.py"] == "modified"
    assert types_by_path["c.py"] == "added"
    assert types_by_path["d.py"] == "deleted"
    assert types_by_path["e.py"] == "untracked"


def test_iteration_start_emits_started_event() -> None:
    emitter, observer = _make_emitter()
    ctx = emitter.start_iteration(iteration_id="it-1", iteration_index=1)

    assert ctx.iteration_id == "it-1"
    assert ctx.iteration_index == 1
    started = observer.events_of(IterationStarted)
    assert len(started) == 1
    assert started[0].record.iteration_id == "it-1"


def test_start_agent_execution_emits_started_event() -> None:
    emitter, observer = _make_emitter()
    ctx = IterationContext(iteration_id="it-1", iteration_index=1)
    agent_execution_id, hooks = emitter.start_agent_execution(
        ctx,
        run_agent_id="ra-1",
        execution_index=1,
    )

    assert "it01-agent01" in agent_execution_id
    started = observer.events_of(AgentExecutionStarted)
    assert len(started) == 1
    assert started[0].record.agent_execution_id == agent_execution_id


def test_finish_agent_execution_emits_finished_event() -> None:
    emitter, observer = _make_emitter()
    ctx = IterationContext(iteration_id="it-1", iteration_index=1)
    agent_execution_id = "run-1-it01-agent01"

    emitter.finish_agent_execution(
        ctx,
        agent_execution_id=agent_execution_id,
        started_at="2026-01-01T00:00:00+00:00",
        run_agent_id="ra-1",
        execution_index=1,
        status="failed",
        error_type="RuntimeError",
        error_message_short="Connection error.",
        tool_calls_count=0,
        duration_seconds=1.23,
    )

    finished = observer.events_of(AgentExecutionFinished)
    assert len(finished) == 1
    record = finished[0].record
    assert record.status == "failed"
    assert record.error_type == "RuntimeError"
    assert record.error_message_short == "Connection error."


def test_record_test_execution_at_run_level() -> None:
    emitter, observer = _make_emitter()

    emitter.record_test_execution(
        None,
        phase="baseline",
        command="pytest",
        exit_code=0,
        timed_out=False,
        signature="abc123",
        iteration=0,
    )

    test_events = observer.events_of(TestExecuted)
    assert len(test_events) == 1
    assert test_events[0].record.run_id == "run-1"
    assert test_events[0].record.phase == "baseline"


def test_record_facade_input() -> None:
    emitter, observer = _make_emitter()
    ctx = IterationContext(iteration_id="it-1", iteration_index=1)
    emitter.record_facade_input(ctx, "Fix the parser.")

    facade = observer.events_of(FacadeInput)
    assert len(facade) == 1
    assert facade[0].record.input_text == "Fix the parser."
    assert facade[0].record.iteration_id == "it-1"


def test_provider_call_forwarded() -> None:
    from llm_autofix_agents.observability.models import ProviderCallRecord

    emitter, observer = _make_emitter()
    emitter.emit_provider_call(
        ProviderCallRecord(
            provider_call_id="pc-1",
            run_id="run-1",
            iteration_id="it-1",
            agent_execution_id="ae-1",
            event_type="retryable_failure",
            attempt=1,
            total_attempts=3,
            status_code=500,
            error_type="RuntimeError",
            error_message_short="boom",
            tool_calls_count=2,
        )
    )

    provider_events = observer.events_of(ProviderCallHappened)
    assert len(provider_events) == 1
    assert provider_events[0].record.event_type == "retryable_failure"
    assert provider_events[0].record.attempt == 1
