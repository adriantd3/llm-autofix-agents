from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from llm_autofix_agents.batch.config import BatchConfig, BugEntry, DatasetConfig


@dataclass(frozen=True, slots=True)
class PreparedExecutionCase:
    case_id: str
    dataset_name: str
    dataset_type: str
    host_workspace: Path
    container_workspace: str
    test_command: str
    prompt_variables: dict[str, str]
    metadata: dict[str, Any] = field(default_factory=dict)
    cleanup_paths: tuple[Path, ...] = ()
    runner_service: str = "runner"


@dataclass(frozen=True, slots=True)
class DatasetPreparationContext:
    dataset: DatasetConfig
    batch: BatchConfig
    batch_id: str
    host_workspace_root: Path
    container_workspace_root: str


@runtime_checkable
class DatasetAdapter(Protocol):
    type: str

    def prepare_case(
        self,
        context: DatasetPreparationContext,
        bug: BugEntry,
    ) -> PreparedExecutionCase:
        ...
