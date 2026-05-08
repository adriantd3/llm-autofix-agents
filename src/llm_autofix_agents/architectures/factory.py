from __future__ import annotations

from llm_autofix_agents.architectures.config import BuiltArchitecture
from llm_autofix_agents.architectures.handoff import build_multi_agent_handoff_architecture
from llm_autofix_agents.architectures.mono_agent import build_mono_agent_architecture
from llm_autofix_agents.architectures.orchestrator import build_multi_agent_orchestrator_architecture
from llm_autofix_agents.architectures.planner_executor import build_planner_executor_architecture
from llm_autofix_agents.contracts import RunArchitecture
from llm_autofix_agents.llm.settings import LLMSettings


def build_architecture(
    *,
    strategy: str,
    settings: LLMSettings,
    agent_models: dict[str, str] | None = None,
    tool_profile: str | None = None,
) -> BuiltArchitecture:
    try:
        architecture = RunArchitecture(strategy)
    except ValueError:
        raise ValueError(f"Unsupported architecture strategy: {strategy}") from None
    if architecture == RunArchitecture.MONO_AGENT:
        return build_mono_agent_architecture(
            settings=settings,
            agent_models=agent_models,
            tool_profile=tool_profile,
        )
    if architecture == RunArchitecture.MULTI_AGENT_HANDOFF:
        return build_multi_agent_handoff_architecture(
            settings=settings,
            agent_models=agent_models,
        )
    if architecture == RunArchitecture.MULTI_AGENT_ORCHESTRATOR:
        return build_multi_agent_orchestrator_architecture(
            settings=settings,
            agent_models=agent_models,
        )
    if architecture == RunArchitecture.PLANNER_EXECUTOR:
        return build_planner_executor_architecture(
            settings=settings,
            agent_models=agent_models,
        )
    raise ValueError(f"Unsupported architecture strategy: {strategy}")
