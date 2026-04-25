from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class GlobalConfig:
    """Singleton global configuration for the autofix system.

    Holds configuration that is constant throughout a run:
    - LLM settings
    - Tool configuration
    - Observability settings
    - Runtime limits
    """

    max_iterations: int = 3
    test_timeout_seconds: int = 300
    tool_profile: str = "full"
    enable_observability: bool = True
    enable_live_log: bool = False
    sqlite_db_path: Path | None = None
    results_dir: Path = Path("results")
    temp_branch_prefix: str = "autofix"
    ignore_rules: list[str] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def reset(self) -> None:
        with self._lock:
            self.max_iterations = 3
            self.test_timeout_seconds = 300
            self.tool_profile = "full"
            self.enable_observability = True
            self.enable_live_log = False
            self.sqlite_db_path = None
            self.results_dir = Path("results")
            self.temp_branch_prefix = "autofix"
            self.ignore_rules = []

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key):
                    setattr(self, key, value)


global_config = GlobalConfig()
