from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from agents import Agent


@dataclass(frozen=True)
class SubAgentDescriptor:
    agent_name: str
    agent_role: str
    model: str
    instructions: str
    tool_profile: str


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
    sub_agents: tuple[SubAgentDescriptor, ...] = ()
