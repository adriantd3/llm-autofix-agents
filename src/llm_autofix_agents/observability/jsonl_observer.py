from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

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
    utc_now_iso,
)


def _serialize_record(record: Any, event_type: str) -> dict[str, Any]:
    if hasattr(record, "__dataclass_fields__"):
        data = asdict(record)
    elif isinstance(record, dict):
        data = dict(record)
    else:
        data = {"value": str(record)}
    data["event"] = event_type
    data["ts"] = utc_now_iso()
    return data


class JsonlEventObserver:
    def __init__(self, results_dir: Path, run_id: str) -> None:
        self._path = results_dir / run_id / "events.jsonl"
        self._path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def path(self) -> Path:
        return self._path

    def _append(self, data: dict[str, Any]) -> None:
        line = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        with self._path.open("a", encoding="utf-8") as handler:
            handler.write(f"{line}\n")

    def on_run_started(self, *, run: RunDescriptor, started_at: str) -> None:
        data = _serialize_record(run, "run_started")
        data["started_at"] = started_at
        self._append(data)

    def on_run_finished(self, *, run_finished: RunFinishedRecord) -> None:
        self._append(_serialize_record(run_finished, "run_finished"))

    def on_run_agent_registered(self, *, run_id: str, agent: AgentDescriptor, instructions_hash: str | None) -> str:
        data = _serialize_record(agent, "agent_registered")
        data["run_id"] = run_id
        data["instructions_hash"] = instructions_hash
        self._append(data)
        return ""

    def on_iteration_started(self, *, record: IterationRecord) -> None:
        self._append(_serialize_record(record, "iteration_started"))

    def on_iteration_finished(self, *, record: IterationRecord) -> None:
        self._append(_serialize_record(record, "iteration_finished"))

    def on_agent_execution_started(self, *, record: AgentExecutionRecord) -> None:
        self._append(_serialize_record(record, "agent_execution_started"))

    def on_agent_execution_finished(self, *, record: AgentExecutionRecord) -> None:
        self._append(_serialize_record(record, "agent_execution_finished"))

    def on_tool_call(self, *, record: ToolCallRecord) -> None:
        self._append(_serialize_record(record, "tool_call"))

    def on_provider_call_event(self, *, record: ProviderCallRecord) -> None:
        self._append(_serialize_record(record, "provider_call_event"))

    def on_test_execution(self, *, record: TestExecutionRecord) -> None:
        self._append(_serialize_record(record, "test_execution"))

    def on_file_change(self, *, record: FileChangeRecord) -> None:
        self._append(_serialize_record(record, "file_change"))

    def on_agent_handoff(self, *, record: AgentHandoffRecord) -> None:
        self._append(_serialize_record(record, "agent_handoff"))

    def on_facade_input(self, *, record: FacadeInputRecord) -> None:
        self._append(_serialize_record(record, "facade_input"))
