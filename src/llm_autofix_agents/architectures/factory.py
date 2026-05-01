from __future__ import annotations

from llm_autofix_agents.architectures.config import BuiltArchitecture
from llm_autofix_agents.architectures.handoff import build_multi_agent_handoff_architecture
from llm_autofix_agents.architectures.mono_agent import build_mono_agent_architecture
from llm_autofix_agents.llm.settings import LLMSettings


def build_architecture(
    *,
    strategy: str,
    settings: LLMSettings,
    agent_models: dict[str, str] | None = None,
    tool_profile: str | None = None,
) -> BuiltArchitecture:
    if strategy == "mono_agent":
        return build_mono_agent_architecture(
            settings=settings,
            agent_models=agent_models,
            tool_profile=tool_profile,
        )
    if strategy == "multi_agent_handoff":
        return build_multi_agent_handoff_architecture(
            settings=settings,
            agent_models=agent_models,
        )
    raise ValueError(f"Unsupported architecture strategy: {strategy}")
