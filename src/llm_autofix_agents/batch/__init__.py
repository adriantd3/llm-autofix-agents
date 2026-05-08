from __future__ import annotations

from llm_autofix_agents.batch.config import (
    BatchConfig,
    BugEntry,
    DatasetConfig,
    GlobalSettings,
    LLMSettings,
    RepositoryConfig,
    TestConfig,
    expand_bugs,
    load_batch_config,
    load_dataset_config,
)
from llm_autofix_agents.batch.summary import BatchSummary, BugRunResult, new_batch_id


def __getattr__(name: str):
    # Lazy imports to break circular dependency: datasets.base -> batch.config -> batch -> batch.runner -> datasets.base
    if name == "BatchRunner":
        from llm_autofix_agents.batch.runner import BatchRunner
        return BatchRunner
    if name in ("capture_error_output", "generate_prompt"):
        from llm_autofix_agents.batch import prompt as _prompt
        return getattr(_prompt, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "BatchConfig",
    "BatchRunner",
    "BatchSummary",
    "BugEntry",
    "BugRunResult",
    "DatasetConfig",
    "GlobalSettings",
    "LLMSettings",
    "RepositoryConfig",
    "TestConfig",
    "expand_bugs",
    "generate_prompt",
    "load_batch_config",
    "load_dataset_config",
    "new_batch_id",
    "capture_error_output",
]
