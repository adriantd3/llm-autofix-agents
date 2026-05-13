from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

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
from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore

logger = logging.getLogger(__name__)


class Observer(Protocol):
    def emit(self, event: ObservabilityEvent) -> None: ...


class NullObserver:
    def emit(self, event: ObservabilityEvent) -> None:
        del event


class CompositeObserver:
    def __init__(self, observers: Sequence[Observer]) -> None:
        self._observers = list(observers)

    def emit(self, event: ObservabilityEvent) -> None:
        for observer in self._observers:
            try:
                observer.emit(event)
            except Exception:  # pragma: no cover - never crash the APR run
                logger.warning("observer failure on %s", type(event).__name__, exc_info=True)


class SQLiteObserver:
    def __init__(self, store: SQLiteObservabilityStore, *, architecture_name: str = "mono_agent") -> None:
        self._store = store
        self._architecture_name = architecture_name

    def emit(self, event: ObservabilityEvent) -> None:  # noqa: PLR0912
        match event:
            case RunStarted():
                architecture_id = self._store.upsert_architecture(self._architecture_name)
                self._store.insert_run_started(
                    descriptor=event.run,
                    architecture_id=architecture_id,
                    started_at=event.started_at,
                )
            case RunFinished():
                self._store.update_run_finished(event.run_finished)
            case AgentRegistered():
                model_config_id = self._store.upsert_model_config(event.agent.model_config)
                self._store.upsert_run_agent(
                    run_id=event.run_id,
                    descriptor=event.agent,
                    model_config_id=model_config_id,
                    instructions_hash=event.instructions_hash,
                )
            case IterationStarted():
                self._store.insert_iteration(event.record)
            case IterationFinished():
                self._store.insert_iteration(event.record)
            case AgentExecutionStarted():
                self._store.insert_agent_execution(event.record)
            case AgentExecutionFinished():
                self._store.insert_agent_execution(event.record)
            case ToolCalled():
                self._store.insert_tool_call(event.record)
            case ProviderCallHappened():
                self._store.insert_provider_call_event(event.record)
            case TestExecuted():
                self._store.insert_test_execution(event.record)
            case FileChanged():
                self._store.insert_file_change(event.record)
            case AgentHandoff():
                self._store.insert_agent_handoff(event.record)
            case FacadeInput():
                # Intentionally not persisted to SQLite; live.md and events.jsonl only.
                pass
