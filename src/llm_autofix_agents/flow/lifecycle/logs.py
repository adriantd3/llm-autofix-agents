from __future__ import annotations

from llm_autofix_agents.flow.models import TestExecution
from llm_autofix_agents.flow.policies.validation import IterationValidationResult
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState


def build_iteration_logs(
    *,
    cfg: RunConfig,
    iteration: int,
    changed_files: list[str],
    test_execution: TestExecution,
    confidence: float,
) -> list[str]:
    return [
        "stage=agent",
        f"architecture={cfg.architecture_name}",
        f"iteration={iteration}/{cfg.max_iterations}",
        f"changed_files={len(changed_files)}",
        f"proposal_confidence={confidence:.3f}",
        f"test_exit_code={test_execution.exit_code}",
        f"test_signature={test_execution.signature}",
        "toolset=apr-local",
        f"tool_profile={cfg.tool_profile}",
        f"tool_count={cfg.tool_count}",
        f"provider={cfg.settings.provider.value}",
        f"model={cfg.settings.model}",
    ]


def record_validation_logs(*, state: RunState, validation: IterationValidationResult) -> None:
    if "proposal_matches_observed_files" not in validation.details:
        return
    state.accumulated_logs.append(
        f"proposal_matches_observed_files={str(validation.details['proposal_matches_observed_files']).lower()}"
    )
