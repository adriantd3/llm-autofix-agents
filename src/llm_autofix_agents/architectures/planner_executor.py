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

from typing import TYPE_CHECKING

from llm_autofix_agents.agents.instructions import (
    EXECUTOR_INSTRUCTIONS,
    PLANNER_INSTRUCTIONS,
)
from llm_autofix_agents.architectures.config import BuiltArchitecture, SubAgentDescriptor
from llm_autofix_agents.flow.strategy import IterationStrategy, PhasedIterationStrategy, PlannerStopPolicy
from llm_autofix_agents.llm.agent_factory import build_agent
from llm_autofix_agents.llm.agent_models import resolve_agent_model
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.tools.profiles import build_apr_tools

if TYPE_CHECKING:
    from llm_autofix_agents.flow.iteration.runner import IterationRunner
    from llm_autofix_agents.flow.lifecycle.finalizer import RunFinalizer
    from llm_autofix_agents.flow.lifecycle.output_builder import RunOutputBuilder
    from llm_autofix_agents.flow.policies.stop import StopPolicy
    from llm_autofix_agents.flow.workspace.manager import WorkspaceManager


def build_planner_executor_architecture(
    *,
    settings: LLMSettings,
    agent_models: dict[str, str] | None = None,
) -> BuiltArchitecture:
    """Build a 2-phase planner-executor architecture.

    Uses a PhasedIterationStrategy that runs the planner in iteration 1
    (with a stop policy that never declares success), then the executor
    in iteration 2+ (with normal stop logic).

    The system's iteration mechanism naturally passes the planner's output
    (reasoning_summary, notes) to iteration 2 via the continuation snapshot.
    """
    planner_tools = build_apr_tools("planner")
    executor_tools = build_apr_tools("executor")
    _all_tools = planner_tools + executor_tools
    unique_tool_count = len({t.__name__ for t in _all_tools if hasattr(t, "__name__")})

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

    def build_planner_agent():
        return build_agent(
            settings=settings,
            name="planner",
            instructions=PLANNER_INSTRUCTIONS,
            tools=planner_tools,
            model_override=planner_model,
            output_schema=None,
        )

    def build_executor_agent():
        return build_agent(
            settings=settings,
            name="executor",
            instructions=EXECUTOR_INSTRUCTIONS,
            tools=executor_tools,
            model_override=executor_model,
            output_schema=None,
        )

    def _build_phased_strategy(
        iteration_runner: IterationRunner,
        workspace: WorkspaceManager,
        output_builder: RunOutputBuilder,
        finalizer: RunFinalizer,
        stop_policy: StopPolicy,
    ) -> IterationStrategy:
        from llm_autofix_agents.flow.iteration.runner import IterationRunner as _IR

        planner_runner = _IR(
            agent_runner=iteration_runner.agent_runner,
            workspace=workspace,
            output_builder=output_builder,
            stop_policy=PlannerStopPolicy(),
        )
        return PhasedIterationStrategy(
            planner_runner=planner_runner,
            executor_runner=iteration_runner,
            workspace=workspace,
            output_builder=output_builder,
            finalizer=finalizer,
            planner_agent_builder=build_planner_agent,
            executor_agent_builder=build_executor_agent,
        )

    return BuiltArchitecture(
        architecture_name="planner_executor",
        facade_agent_builder=build_executor_agent,
        agent_name="planner",
        agent_role="planner",
        agent_model=planner_model,
        instructions=PLANNER_INSTRUCTIONS,
        tool_profile="planner",
        tool_count=unique_tool_count,
        sub_agents=(
            SubAgentDescriptor(
                agent_name="executor",
                agent_role="executor",
                model=executor_model,
                instructions=EXECUTOR_INSTRUCTIONS,
                tool_profile="executor",
            ),
        ),
        iteration_strategy_factory=_build_phased_strategy,
    )
