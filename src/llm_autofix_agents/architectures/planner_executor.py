"""Planner-Executor architecture: separation of reasoning and action.

Philosophy:
- The Planner investigates thoroughly (read, search, test) and produces a complete repair plan.
- The Executor receives the plan, applies the fix, validates, and reports the structured result.

Key differences from other architectures:
- vs mono_agent: explicit separation of investigation and implementation phases.
- vs multi_agent_handoff (4 agents): only 1 handoff boundary → less context loss, more turn budget per phase.
- vs multi_agent_orchestrator: no central manager → each agent has full autonomy in its phase.

The Executor produces the final AgentFixIterationRecord directly (it's the terminal agent).
"""

from __future__ import annotations

from agents import Agent

from llm_autofix_agents.agents.instructions import (
    EXECUTOR_INSTRUCTIONS,
    PLANNER_INSTRUCTIONS,
)
from llm_autofix_agents.architectures.config import BuiltArchitecture, SubAgentDescriptor
from llm_autofix_agents.llm.agent_factory import build_agent
from llm_autofix_agents.llm.agent_models import resolve_agent_model
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.tools.profiles import build_apr_tools


def build_planner_executor_architecture(
    *,
    settings: LLMSettings,
    agent_models: dict[str, str] | None = None,
) -> BuiltArchitecture:
    """Build a 2-phase planner-executor architecture.

    Instead of using SDK handoffs (which don't reliably trigger tool use in
    local models after receiving control), this uses iteration-based phasing:
    - Iteration 1: Planner agent (read-only tools, produces plan as output)
    - Iteration 2+: Executor agent (edit tools, applies plan from continuation context)

    The system's iteration mechanism naturally passes the planner's output
    (reasoning_summary, notes) to iteration 2 via the continuation snapshot.
    """
    planner_tools = build_apr_tools("planner")
    executor_tools = build_apr_tools("executor")
    tool_names = {
        tool.__name__
        for tool in (planner_tools + executor_tools)
        if hasattr(tool, "__name__")
    }

    planner_model = resolve_agent_model(
        agent_models,
        role="planner",
        default_model=settings.model,
    )
    executor_model = resolve_agent_model(
        agent_models,
        role="executor",
        default_model=settings.model,
    )

    # Track which phase we're in via a mutable counter.
    # Iteration 1 = planner, iteration 2+ = executor.
    _iteration_counter: list[int] = [0]

    def build_facade_agent() -> Agent[object]:
        _iteration_counter[0] += 1
        iteration = _iteration_counter[0]

        if iteration == 1:
            # Phase 1: Planner investigates and produces the repair plan.
            # No output_schema so the model doesn't have a "final_output" escape
            # hatch — it must call tools to make progress. Text output is parsed
            # into AgentFixIterationRecord by the provider fallback path.
            return build_agent(
                settings=settings,
                name="planner",
                instructions=PLANNER_INSTRUCTIONS,
                tools=planner_tools,
                model_override=planner_model,
                output_schema=None,
            )
        else:
            # Phase 2+: Executor applies the fix using edit tools.
            # Also no output_schema to force tool use.
            return build_agent(
                settings=settings,
                name="executor",
                instructions=EXECUTOR_INSTRUCTIONS,
                tools=executor_tools,
                model_override=executor_model,
                output_schema=None,
            )

    return BuiltArchitecture(
        architecture_name="planner_executor",
        facade_agent_builder=build_facade_agent,
        agent_name="planner",
        agent_role="planner",
        agent_model=planner_model,
        instructions=PLANNER_INSTRUCTIONS,
        tool_profile="planner",
        tool_count=len(tool_names),
        sub_agents=(
            SubAgentDescriptor(
                agent_name="executor",
                agent_role="executor",
                model=executor_model,
                instructions=EXECUTOR_INSTRUCTIONS,
                tool_profile="executor",
            ),
        ),
    )
