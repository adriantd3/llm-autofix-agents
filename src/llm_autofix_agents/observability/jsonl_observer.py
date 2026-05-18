from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

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
    RunErrored,
    RunFinished,
    RunStarted,
    TestExecuted,
    ToolCalled,
)
from llm_autofix_agents.observability.models import utc_now_iso


def _serialize(record: Any, event_type: str) -> dict[str, Any]:
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

    def emit(self, event: ObservabilityEvent) -> None:
        match event:
            case RunStarted():
                data = _serialize(event.run, "run_started")
                data["started_at"] = event.started_at
                self._append(data)
            case RunFinished():
                self._append(_serialize(event.run_finished, "run_finished"))
            case AgentRegistered():
                data = _serialize(event.agent, "agent_registered")
                data["run_id"] = event.run_id
                data["run_agent_id"] = event.run_agent_id
                data["instructions_hash"] = event.instructions_hash
                self._append(data)
            case IterationStarted():
                self._append(_serialize(event.record, "iteration_started"))
            case IterationFinished():
                self._append(_serialize(event.record, "iteration_finished"))
            case AgentExecutionStarted():
                self._append(_serialize(event.record, "agent_execution_started"))
            case AgentExecutionFinished():
                self._append(_serialize(event.record, "agent_execution_finished"))
            case ToolCalled():
                self._append(_serialize(event.record, "tool_call"))
            case ProviderCallHappened():
                self._append(_serialize(event.record, "provider_call_event"))
            case TestExecuted():
                self._append(_serialize(event.record, "test_execution"))
            case FileChanged():
                self._append(_serialize(event.record, "file_change"))
            case AgentHandoff():
                self._append(_serialize(event.record, "agent_handoff"))
            case FacadeInput():
                self._append(_serialize(event.record, "facade_input"))
            case RunErrored():
                self._append(
                    {
                        "event": "run_errored",
                        "run_id": event.run_id,
                        "error_type": event.error_type,
                        "error_message": event.error_message,
                        "error_category": event.error_category,
                        "traceback": event.traceback,
                        "occurred_at": event.occurred_at,
                        "ts": utc_now_iso(),
                    }
                )
