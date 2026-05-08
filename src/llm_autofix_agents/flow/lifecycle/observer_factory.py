from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_autofix_agents.flow.observability_stack import ObservabilityStack
from llm_autofix_agents.observability import (
    CompositeObserver,
    ConsoleObserver,
    JsonlEventObserver,
    MarkdownLiveObserver,
    NullObserver,
    RunObserver,
    SQLiteObservabilityStore,
)
from llm_autofix_agents.observability.telemetry import RunTelemetry

__all__ = ["ObservabilityStack", "build_observer"]


def build_observer(
    *,
    config: Any,
    repo_root: Path,
    run_id: str,
    architecture_name: str,
) -> ObservabilityStack:
    from llm_autofix_agents.observability import SQLiteObserver

    observers: list[RunObserver] = []
    sqlite_store: SQLiteObservabilityStore | None = None
    live_observer: MarkdownLiveObserver | None = None

    if config.enabled:
        sqlite_store = SQLiteObservabilityStore(db_path=config.sqlite_db_path)
        sqlite_store.initialize()
        observers.append(SQLiteObserver(sqlite_store, architecture_name=architecture_name))
        if getattr(config, "jsonl_enabled", True):
            observers.append(JsonlEventObserver(config.results_dir, run_id))
        if config.live_log_enabled:
            live_observer = MarkdownLiveObserver(config.results_dir / run_id / "live.md")
            observers.append(live_observer)
        if config.interactive:
            observers.append(ConsoleObserver())

    observer = CompositeObserver(observers) if observers else NullObserver()
    telemetry = RunTelemetry(observer=observer, run_id=run_id)
    return ObservabilityStack(
        telemetry=telemetry,
        sqlite_store=sqlite_store,
        live_observer=live_observer,
    )
