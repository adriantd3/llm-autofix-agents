from __future__ import annotations

from llm_autofix_agents.agents.instructions import BASELINE_APR_INSTRUCTIONS
from llm_autofix_agents.architectures import MonoAgentArchitecture
from llm_autofix_agents.contracts import RunInput, RunOutput
from llm_autofix_agents.flow.orchestrator import RunOrchestrator
from llm_autofix_agents.llm.provider import LLMProvider, create_provider
from llm_autofix_agents.llm.settings import LLMSettings


def run_agent_baseline(
    run_input: RunInput,
    *,
    settings: LLMSettings | None = None,
    provider: LLMProvider | None = None,
) -> RunOutput:
    """Run the baseline mono-agent architecture.

    This module is intentionally a small public facade. Runtime mechanics live in
    ``flow`` and architecture-specific behavior lives in ``architectures``.
    """
    resolved_settings = settings if settings is not None else LLMSettings.from_env()
    resolved_provider = provider if provider is not None else create_provider(resolved_settings)

    return RunOrchestrator(
        architecture=MonoAgentArchitecture(instructions=BASELINE_APR_INSTRUCTIONS),
    ).run(
        run_input=run_input,
        settings=resolved_settings,
        provider=resolved_provider,
    )
