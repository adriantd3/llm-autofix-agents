from __future__ import annotations

from llm_autofix_agents.architectures import build_architecture
from llm_autofix_agents.contracts import RunInput, RunOutput
from llm_autofix_agents.flow.orchestrator import RunOrchestrator
from llm_autofix_agents.flow.runtime.options import resolve_tool_profile
from llm_autofix_agents.llm.provider import LLMProvider, create_provider
from llm_autofix_agents.llm.settings import LLMSettings


def run_agent_baseline(
    run_input: RunInput,
    *,
    settings: LLMSettings | None = None,
    provider: LLMProvider | None = None,
    architecture: str | None = None,
    tool_profile: str | None = None,
) -> RunOutput:
    """Run the baseline mono-agent architecture.

    This module is intentionally a small public facade. Runtime mechanics live in
    ``flow`` and architecture-specific behavior lives in ``architectures``.
    """
    resolved_settings = settings if settings is not None else LLMSettings.from_env()
    resolved_provider = provider if provider is not None else create_provider(resolved_settings)
    resolved_architecture = build_architecture(
        strategy=architecture or "mono_agent",
        settings=resolved_settings,
        tool_profile=tool_profile or resolve_tool_profile(run_input.metadata),
    )

    return RunOrchestrator(
        architecture=resolved_architecture,
    ).run(
        run_input=run_input,
        settings=resolved_settings,
        provider=resolved_provider,
    )
