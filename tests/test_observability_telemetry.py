"""Tests for Emitter.record_test_execution (replaces old RunTelemetry tests)."""
from __future__ import annotations

from typing import Any

from llm_autofix_agents.observability.emitter import Emitter
from llm_autofix_agents.observability.events import ObservabilityEvent, TestExecuted


class _CaptureObserver:
    def __init__(self) -> None:
        self.events: list[ObservabilityEvent] = []

    def emit(self, event: ObservabilityEvent) -> None:
        self.events.append(event)


def test_emitter_records_test_execution() -> None:
    observer = _CaptureObserver()
    emitter = Emitter(observer=observer, run_id="run-1")

    emitter.record_test_execution(
        None,
        phase="iteration_validation",
        command="pytest",
        exit_code=0,
        timed_out=False,
        signature="abc123",
        iteration=1,
        agent_execution_id="agent-1",
    )

    test_events = [e for e in observer.events if isinstance(e, TestExecuted)]
    assert len(test_events) == 1
    assert test_events[0].record.run_id == "run-1"
    assert test_events[0].record.phase == "iteration_validation"
