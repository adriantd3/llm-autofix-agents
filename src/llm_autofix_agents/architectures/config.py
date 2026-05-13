from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from agents import Agent

if TYPE_CHECKING:
    from llm_autofix_agents.flow.strategy import IterationStrategyFactory

# Lazy factory that creates a fresh Agent instance per iteration.
#
# MUST be a factory (not a pre-built Agent) because the OpenAI Agents SDK
# accumulates mutable state inside Agent objects (ContextVars for handoff
# notes, hook counters, etc.). Reusing a single Agent across iterations
# would cause state contamination between runs.
AgentFactory = Callable[[], Agent[Any]]


@dataclass(frozen=True)
class SubAgent:
    """Documents a sub-agent that participates in (or is wired into) the architecture.

    When participates_in_run_loop=True (default), the agent is registered in the
    run_agents table and its tool_calls/handoffs reference it.

    When participates_in_run_loop=False, the agent is invoked via Agent.as_tool()
    and is invisible at the SDK lifecycle level. It is documented here but NOT
    registered in run_agents — its work surfaces only through the tool call record
    of the wrapper tool (e.g. explore_code).
    """

    agent_name: str
    agent_role: str
    model: str
    instructions: str
    tool_profile: str
    participates_in_run_loop: bool = True


# Keep the old name as an alias so existing code that imports SubAgentDescriptor
# continues to work during the SH4 transition.
SubAgentDescriptor = SubAgent


@dataclass(frozen=True)
class BuiltArchitecture:
    architecture_name: str
    facade_agent_builder: AgentFactory
    agent_name: str
    agent_role: str
    instructions: str
    tool_profile: str
    tool_count: int
    agent_model: str | None = None
    sub_agents: tuple[SubAgent, ...] = ()
    iteration_strategy_factory: IterationStrategyFactory | None = None
    """Optional factory that builds an architecture-specific iteration strategy.

    When provided, the RunOrchestrator uses this factory instead of the
    default StandardIterationStrategy. This allows architectures like
    planner-executor to control their own iteration loop and phase logic.
    """
