from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Protocol

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
from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore

logger = logging.getLogger(__name__)


class RunObserver(Protocol):
    def on_run_started(self, *, run: RunDescriptor, started_at: str) -> None: ...

    def on_run_finished(self, *, run_finished: RunFinishedRecord) -> None: ...

    def on_run_agent_registered(self, *, run_id: str, agent: AgentDescriptor, instructions_hash: str | None) -> str: ...

    def on_iteration_started(self, *, record: IterationRecord) -> None: ...

    def on_iteration_finished(self, *, record: IterationRecord) -> None: ...

    def on_agent_execution_started(self, *, record: AgentExecutionRecord) -> None: ...

    def on_agent_execution_finished(self, *, record: AgentExecutionRecord) -> None: ...

    def on_tool_call(self, *, record: ToolCallRecord) -> None: ...

    def on_provider_call_event(self, *, record: ProviderCallRecord) -> None: ...

    def on_test_execution(self, *, record: TestExecutionRecord) -> None: ...

    def on_file_change(self, *, record: FileChangeRecord) -> None: ...

    def on_agent_handoff(self, *, record: AgentHandoffRecord) -> None: ...

    def on_facade_input(self, *, record: FacadeInputRecord) -> None: ...


class NullObserver:
    def on_run_started(self, *, run: RunDescriptor, started_at: str) -> None:
        del run, started_at

    def on_run_finished(self, *, run_finished: RunFinishedRecord) -> None:
        del run_finished

    def on_run_agent_registered(self, *, run_id: str, agent: AgentDescriptor, instructions_hash: str | None) -> str:
        del run_id, agent, instructions_hash
        return ""

    def on_iteration_started(self, *, record: IterationRecord) -> None:
        del record

    def on_iteration_finished(self, *, record: IterationRecord) -> None:
        del record

    def on_agent_execution_started(self, *, record: AgentExecutionRecord) -> None:
        del record

    def on_agent_execution_finished(self, *, record: AgentExecutionRecord) -> None:
        del record

    def on_tool_call(self, *, record: ToolCallRecord) -> None:
        del record

    def on_provider_call_event(self, *, record: ProviderCallRecord) -> None:
        del record

    def on_test_execution(self, *, record: TestExecutionRecord) -> None:
        del record

    def on_file_change(self, *, record: FileChangeRecord) -> None:
        del record

    def on_agent_handoff(self, *, record: AgentHandoffRecord) -> None:
        del record

    def on_facade_input(self, *, record: FacadeInputRecord) -> None:
        del record


class CompositeObserver:
    def __init__(self, observers: Sequence[RunObserver]) -> None:
        self._observers = list(observers)

    def on_run_started(self, *, run: RunDescriptor, started_at: str) -> None:
        self._dispatch("on_run_started", run=run, started_at=started_at)

    def on_run_finished(self, *, run_finished: RunFinishedRecord) -> None:
        self._dispatch("on_run_finished", run_finished=run_finished)

    def on_run_agent_registered(self, *, run_id: str, agent: AgentDescriptor, instructions_hash: str | None) -> str:
        last_run_agent_id = ""
        for observer in self._observers:
            try:
                result = observer.on_run_agent_registered(
                    run_id=run_id,
                    agent=agent,
                    instructions_hash=instructions_hash,
                )
                if result:
                    last_run_agent_id = result
            except Exception:  # pragma: no cover - never crash the APR run
                logger.warning("observer failure on_run_agent_registered", exc_info=True)
        return last_run_agent_id

    def on_iteration_started(self, *, record: IterationRecord) -> None:
        self._dispatch("on_iteration_started", record=record)

    def on_iteration_finished(self, *, record: IterationRecord) -> None:
        self._dispatch("on_iteration_finished", record=record)

    def on_agent_execution_started(self, *, record: AgentExecutionRecord) -> None:
        self._dispatch("on_agent_execution_started", record=record)

    def on_agent_execution_finished(self, *, record: AgentExecutionRecord) -> None:
        self._dispatch("on_agent_execution_finished", record=record)

    def on_tool_call(self, *, record: ToolCallRecord) -> None:
        self._dispatch("on_tool_call", record=record)

    def on_provider_call_event(self, *, record: ProviderCallRecord) -> None:
        self._dispatch("on_provider_call_event", record=record)

    def on_test_execution(self, *, record: TestExecutionRecord) -> None:
        self._dispatch("on_test_execution", record=record)

    def on_file_change(self, *, record: FileChangeRecord) -> None:
        self._dispatch("on_file_change", record=record)

    def on_agent_handoff(self, *, record: AgentHandoffRecord) -> None:
        self._dispatch("on_agent_handoff", record=record)

    def on_facade_input(self, *, record: FacadeInputRecord) -> None:
        self._dispatch("on_facade_input", record=record)

    def _dispatch(self, event_name: str, **kwargs: object) -> None:
        for observer in self._observers:
            try:
                getattr(observer, event_name)(**kwargs)
            except Exception:  # pragma: no cover - never crash the APR run
                logger.warning("observer failure on %s", event_name, exc_info=True)


class SQLiteObserver:
    def __init__(self, store: SQLiteObservabilityStore, *, architecture_name: str = "mono_agent") -> None:
        self._store = store
        self._architecture_name = architecture_name
        self._run_agent_ids: dict[str, str] = {}

    def on_run_started(self, *, run: RunDescriptor, started_at: str) -> None:
        architecture_id = self._store.upsert_architecture(self._architecture_name)
        self._store.insert_run_started(descriptor=run, architecture_id=architecture_id, started_at=started_at)

    def on_run_finished(self, *, run_finished: RunFinishedRecord) -> None:
        self._store.update_run_finished(run_finished)

    def on_run_agent_registered(self, *, run_id: str, agent: AgentDescriptor, instructions_hash: str | None) -> str:
        model_config_id = self._store.upsert_model_config(agent.model_config)
        run_agent_id = self._store.upsert_run_agent(
            run_id=run_id,
            descriptor=agent,
            model_config_id=model_config_id,
            instructions_hash=instructions_hash,
        )
        key = f"{run_id}:{agent.agent_name}:{agent.agent_role}"
        self._run_agent_ids[key] = run_agent_id
        return run_agent_id

    def on_iteration_started(self, *, record: IterationRecord) -> None:
        self._store.insert_iteration(record)

    def on_iteration_finished(self, *, record: IterationRecord) -> None:
        self._store.insert_iteration(record)

    def on_agent_execution_started(self, *, record: AgentExecutionRecord) -> None:
        self._store.insert_agent_execution(record)

    def on_agent_execution_finished(self, *, record: AgentExecutionRecord) -> None:
        self._store.insert_agent_execution(record)

    def on_tool_call(self, *, record: ToolCallRecord) -> None:
        self._store.insert_tool_call(record)

    def on_provider_call_event(self, *, record: ProviderCallRecord) -> None:
        self._store.insert_provider_call_event(record)

    def on_test_execution(self, *, record: TestExecutionRecord) -> None:
        self._store.insert_test_execution(record)

    def on_file_change(self, *, record: FileChangeRecord) -> None:
        self._store.insert_file_change(record)

    def on_agent_handoff(self, *, record: AgentHandoffRecord) -> None:
        self._store.insert_agent_handoff(record)

    def on_facade_input(self, *, record: FacadeInputRecord) -> None:
        # Intentionally not persisted to SQLite; live.md and events.jsonl only.
        del record
