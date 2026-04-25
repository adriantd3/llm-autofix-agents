from __future__ import annotations

from llm_autofix_agents.contracts import RunInput
from llm_autofix_agents.flow.models import TestExecution


def build_iteration_input(
    *,
    prompt: str,
    iteration: int,
    max_iterations: int,
    previous_message: str | None,
) -> str:
    if previous_message is None:
        return prompt
    return (
        f"[ITERATION {iteration}/{max_iterations}]\n"
        f"Previous attempt summary:\n{previous_message}\n\n"
        "Continue improving the repair strategy and validate with available tools.\n"
        f"Original prompt:\n{prompt}"
    )


def is_no_progress(
    *,
    previous_message: str | None,
    current_message: str,
    previous_status: str | None,
    current_status: str,
    previous_confidence: float | None,
    current_confidence: float,
    previous_test_signature: str | None,
    current_test_signature: str,
    changed_files: list[str],
) -> bool:
    if previous_message is None or previous_test_signature is None:
        return False

    previous_normalized = " ".join(previous_message.split()).strip().lower()
    current_normalized = " ".join(current_message.split()).strip().lower()
    same_message = previous_normalized == current_normalized
    same_test_signature = previous_test_signature == current_test_signature
    no_file_changes = len(changed_files) == 0

    normalized_status = current_status.strip().lower()
    normalized_previous_status = previous_status.strip().lower() if previous_status is not None else None

    if no_file_changes and same_test_signature and normalized_status == "stuck":
        return True
    if (
        no_file_changes
        and same_test_signature
        and normalized_previous_status == "stuck"
        and normalized_status == "stuck"
    ):
        return True

    if previous_confidence is None:
        return same_message and same_test_signature and no_file_changes

    confidence_not_improving = current_confidence <= previous_confidence + 1e-9
    same_or_worse_state = no_file_changes and same_test_signature and confidence_not_improving
    return same_message and same_or_worse_state


def can_complete_early(*, run_input: RunInput, test_execution: TestExecution) -> bool:
    if run_input.test_command is None:
        return True
    return test_execution.exit_code == 0 and not test_execution.timed_out


def is_regression(*, baseline: TestExecution, current: TestExecution) -> bool:
    return baseline.exit_code == 0 and current.exit_code != 0


def _proposal_signature(proposal) -> str:
    status = proposal.status.strip().lower()
    reasoning_summary = " ".join(proposal.reasoning_summary.split()).strip().lower()
    changed = "|".join(proposal.changed_files)
    notes = " ".join((proposal.notes or "").split()).strip().lower()
    return f"status={status}|reasoning_summary={reasoning_summary}|changed={changed}|notes={notes}"
