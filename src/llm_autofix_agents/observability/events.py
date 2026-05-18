"""Discriminated event union for the flat Observer protocol.

Each event is a frozen dataclass with a `Literal` event_type so match dispatch
is exhaustive and type-safe.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from llm_autofix_agents.observability.models import (
    AgentDescriptor,
    AgentExecutionRecord,
    AgentHandoffRecord,
    FacadeInputRecord,
    FileChangeRecord,
    IterationRecord,
    ProviderCallRecord,
    RunDescriptor,
    RunFinishedRecord,
    TestExecutionRecord,
    ToolCallRecord,
)


@dataclass(frozen=True)
class RunStarted:
    run: RunDescriptor
    started_at: str
    event_type: Literal["run_started"] = field(default="run_started", init=False)


@dataclass(frozen=True)
class RunFinished:
    run_finished: RunFinishedRecord
    event_type: Literal["run_finished"] = field(default="run_finished", init=False)


@dataclass(frozen=True)
class AgentRegistered:
    run_id: str
    run_agent_id: str
    agent: AgentDescriptor
    instructions_hash: str | None
    event_type: Literal["agent_registered"] = field(default="agent_registered", init=False)


@dataclass(frozen=True)
class IterationStarted:
    record: IterationRecord
    event_type: Literal["iteration_started"] = field(default="iteration_started", init=False)


@dataclass(frozen=True)
class IterationFinished:
    record: IterationRecord
    event_type: Literal["iteration_finished"] = field(default="iteration_finished", init=False)


@dataclass(frozen=True)
class AgentExecutionStarted:
    record: AgentExecutionRecord
    event_type: Literal["agent_execution_started"] = field(default="agent_execution_started", init=False)


@dataclass(frozen=True)
class AgentExecutionFinished:
    record: AgentExecutionRecord
    event_type: Literal["agent_execution_finished"] = field(default="agent_execution_finished", init=False)


@dataclass(frozen=True)
class ToolCalled:
    record: ToolCallRecord
    event_type: Literal["tool_called"] = field(default="tool_called", init=False)


@dataclass(frozen=True)
class ProviderCallHappened:
    record: ProviderCallRecord
    event_type: Literal["provider_call_happened"] = field(default="provider_call_happened", init=False)


@dataclass(frozen=True)
class TestExecuted:
    record: TestExecutionRecord
    event_type: Literal["test_executed"] = field(default="test_executed", init=False)


@dataclass(frozen=True)
class FileChanged:
    record: FileChangeRecord
    event_type: Literal["file_changed"] = field(default="file_changed", init=False)


@dataclass(frozen=True)
class AgentHandoff:
    record: AgentHandoffRecord
    event_type: Literal["agent_handoff"] = field(default="agent_handoff", init=False)


@dataclass(frozen=True)
class FacadeInput:
    record: FacadeInputRecord
    event_type: Literal["facade_input"] = field(default="facade_input", init=False)


@dataclass(frozen=True)
class RunErrored:
    run_id: str
    error_type: str
    error_message: str
    error_category: str
    traceback: str | None
    occurred_at: str
    event_type: Literal["run_errored"] = field(default="run_errored", init=False)


ObservabilityEvent = (
    RunStarted
    | RunFinished
    | AgentRegistered
    | IterationStarted
    | IterationFinished
    | AgentExecutionStarted
    | AgentExecutionFinished
    | ToolCalled
    | ProviderCallHappened
    | TestExecuted
    | FileChanged
    | AgentHandoff
    | FacadeInput
    | RunErrored
)
