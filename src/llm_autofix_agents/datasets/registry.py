from __future__ import annotations

from llm_autofix_agents.datasets.base import DatasetAdapter
from llm_autofix_agents.datasets.bugsinpy import BugsInPyAdapter
from llm_autofix_agents.datasets.quixbugs import QuixBugsAdapter

_ADAPTERS: dict[str, DatasetAdapter] = {}


def register(adapter: DatasetAdapter) -> None:
    if adapter.type in _ADAPTERS:
        raise ValueError(f"Dataset adapter '{adapter.type}' is already registered")
    _ADAPTERS[adapter.type] = adapter


register(QuixBugsAdapter())
register(BugsInPyAdapter())


def get(dataset_type: str) -> DatasetAdapter:
    if dataset_type not in _ADAPTERS:
        raise ValueError(
            f"Unknown dataset type '{dataset_type}'. Available types: {', '.join(sorted(_ADAPTERS)) or '(none)'}"
        )
    return _ADAPTERS[dataset_type]


def available_types() -> list[str]:
    return sorted(_ADAPTERS.keys())
