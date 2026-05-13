from __future__ import annotations

import json
import logging
import os
import sys
from typing import Any

from llm_autofix_agents.architectures import build_architecture
from llm_autofix_agents.contracts import ContainerInstantiation, RunInput, RunOutput, RunStatus
from llm_autofix_agents.flow.orchestrator import RunOrchestrator
from llm_autofix_agents.flow.runtime.options import (
    resolve_agent_models,
    resolve_architecture,
    resolve_max_turns,
    resolve_tool_profile,
)
from llm_autofix_agents.flow.workspace.state import resolve_repo_root
from llm_autofix_agents.llm.provider import LLMProvider, create_provider
from llm_autofix_agents.llm.settings import LLMSettings
from llm_autofix_agents.observability import resolve_observability_config
from llm_autofix_agents.repo_source import prepare_target_repository

_DEFAULT_AGENT_PROMPT = "Analyze a failing test and suggest a minimal fix strategy."

logger = logging.getLogger(__name__)


def main() -> int:
    """Execute a single run inside a container from RUN_* environment variables."""
    _configure_logging()

    if not _has_runtime_contract_env():
        logger.error("Missing RUN_* environment variables. RUN_REPOSITORY is required.")
        return 2

    try:
        instantiation = ContainerInstantiation.from_env()
    except ValueError as exc:
        logger.error("Invalid RUN_* runtime configuration: %s", exc)
        return 2

    metadata: dict[str, object] = {"source": "batch-executor"}
    prompt = instantiation.bootstrap_prompt or ""
    test_command = _resolve_optional_text(os.environ.get("RUN_TEST_COMMAND"))
    dataset_type = _resolve_optional_text(os.environ.get("RUN_DATASET_TYPE"))
    dataset_name = _resolve_optional_text(os.environ.get("RUN_DATASET_NAME"))
    bugsinpy_compile_required = _resolve_optional_bool(os.environ.get("RUN_BUGSINPY_COMPILE_REQUIRED"))
    metadata.update(
        {
            "runtime_repository": instantiation.repository,
            "runtime_branch": instantiation.branch,
            "runtime_architecture": instantiation.architecture,
            "runtime_agent_models": instantiation.agent_models,
        }
    )
    if dataset_type is not None:
        metadata["dataset_type"] = dataset_type
    if dataset_name is not None:
        metadata["dataset_name"] = dataset_name
    if bugsinpy_compile_required is not None:
        metadata["bugsinpy_compile_required"] = bugsinpy_compile_required

    try:
        prepared_repo = prepare_target_repository(
            repository=instantiation.repository,
            branch=instantiation.branch,
        )
    except ValueError as exc:
        logger.error("%s", exc)
        return 2

    max_iterations_env = _resolve_optional_text(os.environ.get("AUTOFIX_MAX_ITERATIONS"))
    if max_iterations_env is not None:
        try:
            metadata["max_iterations"] = int(max_iterations_env)
        except ValueError:
            logger.error(
                "AUTOFIX_MAX_ITERATIONS must be an integer, got: %s",
                max_iterations_env,
            )
            return 2

    max_turns_env = _resolve_optional_text(os.environ.get("RUN_MAX_TURNS"))
    if max_turns_env is not None:
        try:
            metadata["max_turns"] = int(max_turns_env)
        except ValueError:
            logger.error(
                "RUN_MAX_TURNS must be an integer, got: %s",
                max_turns_env,
            )
            return 2

    run_input = RunInput(
        prompt=prompt,
        metadata=metadata,
        target_repo=str(prepared_repo.path),
        test_command=test_command,
    )
    try:
        run_output = _run(run_input)
    except ValueError as exc:
        logger.error("Invalid runtime configuration: %s", exc)
        return 2
    except Exception as exc:
        logger.exception("Run execution failed: %s", exc)
        return 1
    finally:
        prepared_repo.cleanup()

    payload = {
        "input": run_input.model_dump(mode="json"),
        "output": run_output.model_dump(mode="json"),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if run_output.status == RunStatus.SUCCESS else 1


def _run(
    run_input: RunInput,
    *,
    settings: LLMSettings | None = None,
    provider: LLMProvider | None = None,
    architecture: str | None = None,
    tool_profile: str | None = None,
) -> RunOutput:
    resolved_settings = settings if settings is not None else LLMSettings.from_env()
    observability_config = resolve_observability_config(
        repo_root=resolve_repo_root(run_input.target_repo),
        metadata=run_input.metadata,
    )
    obs_meta: dict[str, Any] = {
        "observability_enabled": observability_config.enabled,
        "live_log_enabled": observability_config.live_log_enabled,
        "interactive": observability_config.interactive,
        "results_dir": str(observability_config.results_dir),
    }
    if observability_config.sqlite_db_path is not None:
        obs_meta["observability_db"] = str(observability_config.sqlite_db_path)
    run_input.metadata = {**run_input.metadata, **obs_meta}
    resolved_settings = resolved_settings.model_copy(update={"max_turns": resolve_max_turns(run_input.metadata)})
    resolved_provider = provider if provider is not None else create_provider(resolved_settings)
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


def _configure_logging() -> None:
    level_name = os.environ.get("AUTOFIX_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr, force=True)


def _resolve_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _resolve_optional_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y"}:
        return True
    if normalized in {"0", "false", "no", "n"}:
        return False
    return None


def _has_runtime_contract_env() -> bool:
    keys = (
        "RUN_REPOSITORY",
        "RUN_BRANCH",
        "RUN_ARCHITECTURE",
        "RUN_AGENT_MODELS",
    )
    return any(_resolve_optional_text(os.environ.get(key)) is not None for key in keys)


if __name__ == "__main__":
    sys.exit(main())
