from __future__ import annotations

from pathlib import Path
from typing import Any

from llm_autofix_agents.flow.observability_stack import ObservabilityStack
from llm_autofix_agents.observability import (
    JsonlEventObserver,
    MarkdownLiveObserver,
    SQLiteObservabilityStore,
)
from llm_autofix_agents.observability.emitter import Emitter
from llm_autofix_agents.observability.observer import (
    CompositeObserver,
    NullObserver,
    Observer,
    SQLiteObserver,
)

__all__ = ["ObservabilityStack", "build_observer"]


def build_observer(
    *,
    config: Any,
    repo_root: Path,
    run_id: str,
    architecture_name: str,
) -> ObservabilityStack:
    observers: list[Observer] = []
    sqlite_store: SQLiteObservabilityStore | None = None
    live_observer: MarkdownLiveObserver | None = None

    if config.enabled:
        # Per-run DB path: explicit override → use that; else default to run_id/run.db.
        run_db_path = config.sqlite_db_path or (config.results_dir / run_id / "run.db")
        sqlite_store = SQLiteObservabilityStore(db_path=run_db_path)
        sqlite_store.initialize()
        observers.append(SQLiteObserver(sqlite_store, architecture_name=architecture_name))
        if getattr(config, "jsonl_enabled", True):
            observers.append(JsonlEventObserver(config.results_dir, run_id))
        if config.live_log_enabled:
            live_observer = MarkdownLiveObserver(config.results_dir / run_id / "live.md")
            observers.append(live_observer)
        if config.interactive:
            from llm_autofix_agents.observability.interactive import ConsoleObserver
            observers.append(ConsoleObserver())

    observer: Observer = CompositeObserver(observers) if observers else NullObserver()
    emitter = Emitter(observer=observer, run_id=run_id)
    return ObservabilityStack(
        emitter=emitter,
        sqlite_store=sqlite_store,
        live_observer=live_observer,
    )
