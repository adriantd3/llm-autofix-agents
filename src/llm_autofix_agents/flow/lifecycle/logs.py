from __future__ import annotations

from llm_autofix_agents.flow.models import TestExecution
from llm_autofix_agents.flow.policies.validation import IterationValidationResult
from llm_autofix_agents.flow.runtime.context import RunState


def build_iteration_logs(
    *,
    architecture_name: str,
    iteration: int,
    max_iterations: int,
    changed_files: list[str],
    test_execution: TestExecution,
    confidence: float,
    tool_profile: str,
    tool_count: int,
    provider: str,
    model: str,
) -> list[str]:
    return [
        "stage=agent",
        f"architecture={architecture_name}",
        f"iteration={iteration}/{max_iterations}",
        f"changed_files={len(changed_files)}",
        f"proposal_confidence={confidence:.3f}",
        f"test_exit_code={test_execution.exit_code}",
        f"test_signature={test_execution.signature}",
        "toolset=apr-local",
        f"tool_profile={tool_profile}",
        f"tool_count={tool_count}",
        f"provider={provider}",
        f"model={model}",
    ]


def record_validation_logs(*, state: RunState, validation: IterationValidationResult) -> None:
    if "proposal_matches_observed_files" not in validation.details:
        return
    state.accumulated_logs.append(
        f"proposal_matches_observed_files={str(validation.details['proposal_matches_observed_files']).lower()}"
    )

