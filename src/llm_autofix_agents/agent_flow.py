from __future__ import annotations

from llm_autofix_agents.architectures import build_architecture
from llm_autofix_agents.contracts import RunInput, RunOutput
from llm_autofix_agents.flow.orchestrator import RunOrchestrator
from llm_autofix_agents.flow.runtime.options import (
    resolve_agent_models,
    resolve_architecture,
    resolve_tool_profile,
)
from llm_autofix_agents.flow.workspace.state import resolve_repo_root
from llm_autofix_agents.llm.provider import LLMProvider, create_provider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability import resolve_observability_config


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
    observability_config = resolve_observability_config(
        repo_root=resolve_repo_root(run_input.target_repo),
        metadata=run_input.metadata,
    )
    run_input.metadata = {
        **run_input.metadata,
        "observability_enabled": observability_config.enabled,
        "live_log_enabled": observability_config.live_log_enabled,
        "interactive": observability_config.interactive,
        "results_dir": str(observability_config.results_dir),
        "observability_db": str(observability_config.sqlite_db_path),
    }
    resolved_architecture = build_architecture(
        strategy=resolve_architecture(run_input.metadata, explicit=architecture),
        settings=resolved_settings,
        agent_models=resolve_agent_models(run_input.metadata),
        tool_profile=tool_profile or resolve_tool_profile(run_input.metadata),
    )

    return RunOrchestrator(
        architecture=resolved_architecture,
    ).run(
        run_input=run_input,
        settings=resolved_settings,
        provider=resolved_provider,
    )
