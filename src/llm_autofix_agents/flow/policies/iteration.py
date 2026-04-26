from __future__ import annotations

from llm_autofix_agents.flow.models import TestExecution
from llm_autofix_agents.llm.provider import AgentFixIterationRecord

_FAILURE_DRIVEN_INTRO = (
    "You are an autonomous software repair agent. Analyze the failing test results below, "
    "find the root cause in the repository, apply the smallest correct change, rerun the "
    "focused test command, inspect the final diff, and then report the final status. "
    "You must use tools for evidence; do not report edits or passing tests without tool outputs."
)
_MAX_BASELINE_OUTPUT_CHARS = 12_000


def build_iteration_input(
    *,
    prompt: str,
    iteration: int,
    max_iterations: int,
    previous_message: str | None,
    baseline_test_execution: TestExecution | None,
    test_command: str | None,
) -> str:
    if previous_message is None:
        first_iteration_input = _build_first_iteration_input(
            baseline_test_execution=baseline_test_execution,
            test_command=test_command,
        )
        if first_iteration_input is not None:
            return first_iteration_input
        return prompt

    baseline_hint = ""
    if baseline_test_execution is not None:
        baseline_hint = (
            f"\nInitial failing test context: exit_code={baseline_test_execution.exit_code}, "
            f"timed_out={baseline_test_execution.timed_out}, signature={baseline_test_execution.signature}."
        )

    return (
        f"[ITERATION {iteration}/{max_iterations}]\n"
        f"Previous attempt summary:\n{previous_message}\n\n"
        "Continue improving the repair strategy and validate with available tools."
        f"{baseline_hint}"
    )


def _build_first_iteration_input(
    *,
    baseline_test_execution: TestExecution | None,
    test_command: str | None,
) -> str | None:
    if baseline_test_execution is None:
        return None

    if baseline_test_execution.exit_code == 0 and not baseline_test_execution.timed_out:
        return None

    command = (test_command or "").strip() or "<not provided>"
    output = _truncate_text(baseline_test_execution.output, _MAX_BASELINE_OUTPUT_CHARS)

    return (
        f"{_FAILURE_DRIVEN_INTRO}\n\n"
        f"Focused test command:\n{command}\n\n"
        "Initial failing test execution:\n"
        f"- exit_code: {baseline_test_execution.exit_code}\n"
        f"- timed_out: {baseline_test_execution.timed_out}\n"
        f"- signature: {baseline_test_execution.signature}\n\n"
        "Test output:\n"
        f"{output}"
    )


def _truncate_text(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[:max_chars]}\n\n[truncated to {max_chars} chars]"


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

    same_message = _normalize(previous_message) == _normalize(current_message)
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
    return same_message and no_file_changes and same_test_signature and confidence_not_improving


def is_regression(*, baseline: TestExecution, current: TestExecution) -> bool:
    return baseline.exit_code == 0 and current.exit_code != 0


def proposal_signature(proposal: AgentFixIterationRecord) -> str:
    status = proposal.status.strip().lower()
    reasoning_summary = _normalize(proposal.reasoning_summary)
    changed = "|".join(proposal.changed_files)
    notes = _normalize(proposal.notes or "")
    return f"status={status}|reasoning_summary={reasoning_summary}|changed={changed}|notes={notes}"


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip().lower()
