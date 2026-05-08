from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from agents import Agent

if TYPE_CHECKING:
    from llm_autofix_agents.flow.strategy import IterationStrategyFactory


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
    """Lazy factory that creates a fresh Agent instance per iteration.

    MUST be a factory (not a pre-built Agent) because the OpenAI Agents SDK
    accumulates mutable state inside Agent objects (ContextVars for handoff
    notes, hook counters, etc.). Reusing a single Agent across iterations
    would cause state contamination between runs.
    """
    agent_name: str
    agent_role: str
    instructions: str
    tool_profile: str
    tool_count: int
    agent_model: str | None = None
    sub_agents: tuple[SubAgentDescriptor, ...] = ()
    iteration_strategy_factory: IterationStrategyFactory | None = None
    """Optional factory that builds an architecture-specific iteration strategy.

    When provided, the RunOrchestrator uses this factory instead of the
    default StandardIterationStrategy. This allows architectures like
    planner-executor to control their own iteration loop and phase logic.
    """
