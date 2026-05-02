from __future__ import annotations

from llm_autofix_agents.flow.models import TestExecution
from llm_autofix_agents.llm.provider import AgentFixIterationRecord

_FAILURE_DRIVEN_INTRO = (
    "You are an autonomous software repair agent with a LIMITED number of turns. "
    "Analyze the failing test results below, find the root cause in the repository, "
    "apply the smallest correct change, rerun the focused test command, inspect the "
    "final diff, and then report the final status.\n\n"
    "CRITICAL RULES:\n"
    "- NEVER modify test files (anything under test/ or tests/, or files named test_*.py / *_test.py). "
    "If you modify a test file, your iteration is REJECTED and the run ENDS.\n"
    "- Do NOT re-run the failing test before making code changes. The failure output is already below.\n"
    "- Do NOT call the same tool twice with the same arguments. Every redundant call wastes a turn.\n"
    "- Plan your next 2-3 tool calls before making any call.\n\n"
    "You must use tools for evidence; do not report edits or passing tests without tool outputs."
)
_MAX_BASELINE_OUTPUT_CHARS = 12_000


_VALIDATION_FEEDBACK_TEMPLATE = (
    "⚠ VALIDATION REJECTION FROM PREVIOUS ITERATION:\n"
    "{feedback}\n\n"
    "Your changes from the previous iteration have been reverted. "
    "DO NOT repeat the same mistake.\n\n"
)


def build_iteration_input(
    *,
    prompt: str,
    iteration: int,
    max_iterations: int,
    previous_message: str | None,
    baseline_test_execution: TestExecution | None,
    test_command: str | None,
    validation_feedback: str | None = None,
) -> str:
    feedback_prefix = ""
    if validation_feedback:
        feedback_prefix = _VALIDATION_FEEDBACK_TEMPLATE.format(feedback=validation_feedback)

    if previous_message is None:
        first_iteration_input = _build_first_iteration_input(
            baseline_test_execution=baseline_test_execution,
            test_command=test_command,
            validation_feedback=validation_feedback,
        )
        if first_iteration_input is not None:
            return first_iteration_input
        prompt_with_feedback = f"{feedback_prefix}{prompt}" if validation_feedback else prompt
        return prompt_with_feedback

    baseline_hint = ""
    if baseline_test_execution is not None:
        baseline_hint = (
            f"\nInitial failing test context: exit_code={baseline_test_execution.exit_code}, "
            f"timed_out={baseline_test_execution.timed_out}, signature={baseline_test_execution.signature}."
        )

    return (
        f"{feedback_prefix}"
        f"[ITERATION {iteration}/{max_iterations}]\n"
        f"Previous attempt summary:\n{previous_message}\n\n"
        "Continue improving the repair strategy and validate with available tools."
        f"{baseline_hint}"
    )


def _build_first_iteration_input(
    *,
    baseline_test_execution: TestExecution | None,
    test_command: str | None,
    validation_feedback: str | None = None,
) -> str | None:
    if baseline_test_execution is None:
        return None

    if baseline_test_execution.exit_code == 0 and not baseline_test_execution.timed_out:
        return None

    command = (test_command or "").strip() or "<not provided>"
    output = _truncate_text(baseline_test_execution.output, _MAX_BASELINE_OUTPUT_CHARS)

    feedback_prefix = ""
    if validation_feedback:
        feedback_prefix = _VALIDATION_FEEDBACK_TEMPLATE.format(feedback=validation_feedback)

    return (
        f"{feedback_prefix}"
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
    """Return True only when baseline was passing (exit_code==0) and now fails.

    This intentionally does NOT detect "worsening" when both baseline and current fail.
    """
    return baseline.exit_code == 0 and current.exit_code != 0


def proposal_signature(proposal: AgentFixIterationRecord) -> str:
    status = proposal.status.strip().lower()
    reasoning_summary = _normalize(proposal.reasoning_summary)
    notes = _normalize(proposal.notes or "")
    return f"status={status}|reasoning_summary={reasoning_summary}|notes={notes}"


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip().lower()
