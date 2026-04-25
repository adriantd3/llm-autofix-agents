from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_autofix_agents.observability import (
    CompositeObserver,
    ConsoleObserver,
    MarkdownLiveObserver,
    NullObserver,
    RunObserver,
    SQLiteObservabilityStore,
)


def build_observer(
    *,
    config: Any,
    repo_root: Path,
    run_id: str,
    architecture_name: str,
) -> tuple[RunObserver, SQLiteObservabilityStore | None, MarkdownLiveObserver | None]:
    from llm_autofix_agents.observability import SQLiteObserver

    observers: list[RunObserver] = []
    sqlite_store: SQLiteObservabilityStore | None = None
    live_observer: MarkdownLiveObserver | None = None

    if config.enabled:
        sqlite_store = SQLiteObservabilityStore(db_path=config.sqlite_db_path)
        sqlite_store.initialize()
        observers.append(SQLiteObserver(sqlite_store, architecture_name=architecture_name))
        if config.live_log_enabled:
            live_observer = MarkdownLiveObserver(config.results_dir / run_id / "live.md")
            observers.append(live_observer)
        if config.interactive:
            observers.append(ConsoleObserver())

    return (CompositeObserver(observers) if observers else NullObserver()), sqlite_store, live_observer
