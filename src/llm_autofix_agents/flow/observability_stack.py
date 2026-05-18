"""ObservabilityStack — cohesive container for a run's observability components.

This module is intentionally kept at the flow/ level with no imports from
flow/runtime/ or flow/lifecycle/ to avoid circular dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from llm_autofix_agents.observability import MarkdownLiveObserver, SQLiteObservabilityStore
from llm_autofix_agents.observability.emitter import Emitter


@dataclass(frozen=True)
class ObservabilityStack:
    """Encapsulates the full observability stack for a run.

    Owns the emitter API, optional SQLite store, and optional live log.
    Consumers should depend on this object instead of receiving the parts
    separately, which avoids spreading observability internals across RunConfig.
    """

    emitter: Emitter
    sqlite_store: SQLiteObservabilityStore | None
    live_observer: MarkdownLiveObserver | None
    base_results_dir: Path = field(default_factory=lambda: Path("results"))

    def results_dir(self, *, repo_root: Path, run_id: str) -> Path:
        """Resolve the output directory for this run."""
        return self.base_results_dir / run_id

    def live_log_display_path(self, *, repo_root: Path) -> str | None:
        """Return relative path of live log for display, or None if disabled."""
        if self.live_observer is None:
            return None
        return _display_path(self.live_observer.path, repo_root)

    def db_display_path(self, *, repo_root: Path) -> str:
        """Return relative path of SQLite DB for display, or 'disabled'."""
        if self.sqlite_store is None:
            return "disabled"
        return _display_path(self.sqlite_store.db_path, repo_root)


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()
