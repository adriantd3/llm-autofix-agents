from __future__ import annotations

from llm_autofix_agents.architectures.config import BuiltArchitecture
from llm_autofix_agents.architectures.mono_agent import build_mono_agent_architecture
from llm_autofix_agents.llm.settings import LLMSettings


def build_architecture(
    *,
    strategy: str,
    settings: LLMSettings,
    tool_profile: str | None = None,
) -> BuiltArchitecture:
    if strategy != "mono_agent":
        raise ValueError(f"Unsupported architecture strategy: {strategy}")

    return build_mono_agent_architecture(settings=settings, tool_profile=tool_profile)
