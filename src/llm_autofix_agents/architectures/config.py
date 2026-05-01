from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from agents import Agent


@dataclass(frozen=True)
class BuiltArchitecture:
    architecture_name: str
    facade_agent_builder: Callable[[], Agent[Any]]
    agent_name: str
    agent_role: str
    instructions: str
    tool_profile: str
    tool_count: int
    agent_model: str | None = None
