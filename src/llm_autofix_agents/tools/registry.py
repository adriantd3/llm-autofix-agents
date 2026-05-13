"""Tool descriptor registry.

Tool modules call :func:`register` at import time to associate a
:class:`~llm_autofix_agents.tools.metadata.ToolDescriptor` with each tool name.

The observability layer reads the registry via :func:`get` — no tool-module
imports required from the observability package.
"""
from __future__ import annotations

import logging
from typing import Iterator

from llm_autofix_agents.tools.metadata import ToolDescriptor

logger = logging.getLogger(__name__)

_registry: dict[str, ToolDescriptor] = {}


def register(descriptor: ToolDescriptor) -> None:
    """Register a :class:`ToolDescriptor` by its ``name`` field."""
    _registry[descriptor.name] = descriptor


def get(name: str) -> ToolDescriptor | None:
    """Return the descriptor for *name*, or ``None`` if not registered."""
    descriptor = _registry.get(name)
    if descriptor is None:
        logger.warning("No ToolDescriptor registered for tool %r; using fallback summarizers.", name)
    return descriptor


def iter_all() -> Iterator[ToolDescriptor]:
    """Iterate over all registered descriptors."""
    yield from _registry.values()


def registered_names() -> frozenset[str]:
    """Return the set of all registered tool names."""
    return frozenset(_registry)
