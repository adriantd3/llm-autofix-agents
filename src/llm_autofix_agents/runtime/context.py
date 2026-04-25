from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class RuntimeContext:
    """Singleton runtime context holding global state for a run.

    This eliminates the need to pass repo_root, run_id, and other
    common parameters through every function in the call chain.
    """

    repo_root: Path | None = None
    run_id: str | None = None
    run_agent_id: str | None = None
    iteration: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reset(self) -> None:
        with self._lock:
            self.repo_root = None
            self.run_id = None
            self.run_agent_id = None
            self.iteration = 0
            self.metadata = {}

    def set(
        self, repo_root: Path, run_id: str, run_agent_id: str | None = None, metadata: dict[str, Any] | None = None
    ) -> None:
        with self._lock:
            self.repo_root = repo_root
            self.run_id = run_id
            self.run_agent_id = run_agent_id
            self.iteration = 0
            self.metadata = metadata or {}

    def next_iteration(self) -> int:
        with self._lock:
            self.iteration += 1
            return self.iteration

    @property
    def iteration_id(self) -> str | None:
        if self.run_id is None or self.iteration == 0:
            return None
        return f"{self.run_id}-it{self.iteration:02d}"

    @property
    def agent_execution_id(self) -> str | None:
        if self.run_id is None or self.iteration == 0:
            return None
        return f"{self.run_id}-it{self.iteration:02d}-agent01"


runtime_context = RuntimeContext()
