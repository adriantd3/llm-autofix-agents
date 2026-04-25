from __future__ import annotations

from llm_autofix_agents.architectures import MonoAgentArchitecture
from llm_autofix_agents.contracts import RunInput, RunOutput
from llm_autofix_agents.flow.orchestrator import RunOrchestrator
from llm_autofix_agents.llm.provider import LLMProvider, create_provider
from llm_autofix_agents.llm.settings import LLMSettings

_BASELINE_INSTRUCTIONS = (
    "You are an APR baseline agent operating autonomously in an execution-first workflow. "
    "Your goal is to diagnose failing tests or error logs, inspect the repository, "
    "apply a minimal and maintainable fix, "
    "and validate the result using the available local APR tools. "
    "Do not guess from the prompt alone: inspect relevant files and run focused commands/tests when needed. "
    "Prefer small, localized patches. Avoid broad rewrites unless the failure clearly requires them. "
    "Before reporting done, inspect the repository diff and validate with tests "
    "when a test command or test runner is available. "
    "Return a structured iteration report with: status, reasoning_summary, confidence, changed_files, notes. "
    "The runtime independently verifies changed files, diffs, and test results, so be honest about uncertainty."
)


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
        architecture=MonoAgentArchitecture(instructions=_BASELINE_INSTRUCTIONS),
    ).run(
        run_input=run_input,
        settings=resolved_settings,
        provider=resolved_provider,
    )
