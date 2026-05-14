from __future__ import annotations

import re
from pathlib import Path

from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.tools.text import compact_test_output

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
    "- Plan your next 2-3 tool calls before making any call.\n"
    "- If a test traceback shows a test function name, you MUST read the ENTIRE test function "
    "(from 'def test_...' to the next 'def ') to see ALL assertions, not just the failing line.\n"
    "- Before proposing a fix, consider ALL assertions in the test function that involve the code you will change.\n"
    "- Do NOT use execute_command to test Python logic or validate your fix with a subprocess. "
    "Apply your fix directly with replace_in_file, then call run_test_target with the Focused test command.\n\n"
    "- In your final response, populate 'notes' with short bullets: inspected, attempted, changes, results, next.\n\n"
    "You must use tools for evidence; do not report edits or passing tests without tool outputs."
)
_MAX_BASELINE_OUTPUT_CHARS = 4000
_MAX_SNAPSHOT_OUTPUT_CHARS = 2000


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
    latest_snapshot: str | None,
    baseline_test_execution: TestExecution | None,
    test_command: str | None,
    validation_feedback: str | None = None,
    repo_root: Path | None = None,
) -> str:
    feedback_prefix = ""
    if validation_feedback:
        feedback_prefix = _VALIDATION_FEEDBACK_TEMPLATE.format(feedback=validation_feedback)

    if previous_message is None:
        first_iteration_input = _build_first_iteration_input(
            baseline_test_execution=baseline_test_execution,
            test_command=test_command,
            validation_feedback=validation_feedback,
            repo_root=repo_root,
        )
        if first_iteration_input is not None:
            return first_iteration_input
        prompt_with_feedback = f"{feedback_prefix}{prompt}" if validation_feedback else prompt
        return prompt_with_feedback

    snapshot_block = f"\n\n{latest_snapshot}" if latest_snapshot else ""

    # Include baseline test context as a reminder of the ORIGINAL failure.
    # This prevents the model from oscillating (fixing one assertion while breaking another).
    baseline_reminder = ""
    if baseline_test_execution and baseline_test_execution.exit_code != 0:
        baseline_output = compact_test_output(
            baseline_test_execution.output, max_chars=1200
        )
        if baseline_output:
            baseline_reminder = (
                "\n\nORIGINAL baseline failure (this is what you started with — "
                "your fix must address THIS while not breaking other assertions):\n"
                f"{baseline_output}\n"
            )

    # Remind the model of the focused test command so it doesn't guess wrong runners.
    test_command_reminder = ""
    if test_command and test_command.strip():
        test_command_reminder = (
            f"\n\nFocused test command (pass verbatim as `runner` to run_test_target with `cwd=\"\"`):\n"
            f"{test_command.strip()}\n"
        )

    return (
        f"{feedback_prefix}"
        f"[ITERATION {iteration}/{max_iterations}]\n"
        f"Previous attempt summary (agent-reported):\n{previous_message}"
        f"{snapshot_block}"
        f"{baseline_reminder}"
        f"{test_command_reminder}\n\n"
        "Task:\n"
        "Continue improving the repair strategy. Use tools to inspect and edit, "
        "then validate with the test command.\n"
        "IMPORTANT: If your last fix broke a different assertion, you need a fix "
        "that satisfies ALL constraints simultaneously."
    )


def build_continuation_snapshot(
    *,
    proposal: AgentFixIterationRecord,
    changes: WorkspaceChangeSet,
    test_execution: TestExecution,
) -> str:
    compact_output = compact_test_output(test_execution.output, max_chars=_MAX_SNAPSHOT_OUTPUT_CHARS)
    output_block = _indent_block(compact_output or "(no output)", prefix="    ")

    changed_files = changes.all_changed_files
    if changed_files:
        changed_block = "\n".join(f"  - {path}" for path in changed_files)
    else:
        changed_block = "  - (none)"

    notes_block = _format_notes_block(proposal.notes)

    lines = [
        "Observed continuation snapshot (runtime evidence):",
        "- Latest test execution:",
        f"  - exit_code: {test_execution.exit_code}",
        f"  - timed_out: {test_execution.timed_out}",
        f"  - signature: {test_execution.signature}",
        "  - compact_output:",
        output_block,
        "- Changed files observed:",
        changed_block,
    ]
    if not changed_files:
        lines.append(
            "⚠ WARNING: No source files were modified in the previous iteration. "
            "You MUST apply at least one code change before calling run_tests. "
            "Investigate the root cause and edit the relevant source file."
        )
    if changes.diff:
        diff_preview = changes.diff[:800]
        if len(changes.diff) > 800:
            diff_preview += "\n... [truncated]"
        lines.append("- Diff of changes (do NOT repeat the same edit if it failed):")
        lines.append(_indent_block(diff_preview, prefix="    "))
    if notes_block:
        lines.append("- Attempt notes (agent-reported, if present):")
        lines.append(notes_block)

    return "\n".join(lines)


def _build_first_iteration_input(
    *,
    baseline_test_execution: TestExecution | None,
    test_command: str | None,
    validation_feedback: str | None = None,
    repo_root: Path | None = None,
) -> str | None:
    if baseline_test_execution is None:
        return None

    if baseline_test_execution.exit_code == 0 and not baseline_test_execution.timed_out:
        return None

    command = (test_command or "").strip() or "<not provided>"
    output = compact_test_output(baseline_test_execution.output, max_chars=_MAX_BASELINE_OUTPUT_CHARS)

    feedback_prefix = ""
    if validation_feedback:
        feedback_prefix = _VALIDATION_FEEDBACK_TEMPLATE.format(feedback=validation_feedback)

    test_function_block = ""
    if repo_root is not None:
        test_function_block = _extract_failing_test_function(
            test_output=baseline_test_execution.output,
            repo_root=repo_root,
        )

    return (
        f"{feedback_prefix}"
        f"{_FAILURE_DRIVEN_INTRO}\n\n"
        f"Focused test command:\n{command}\n\n"
        "Initial failing test execution:\n"
        f"- exit_code: {baseline_test_execution.exit_code}\n"
        f"- timed_out: {baseline_test_execution.timed_out}\n"
        f"- signature: {baseline_test_execution.signature}\n\n"
        "Compact test output:\n"
        f"{output}"
        f"{test_function_block}"
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


def _indent_block(text: str, *, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def _format_notes_block(notes: str | None, *, max_lines: int = 8) -> str:
    if not notes:
        return ""

    lines = [line.strip() for line in notes.splitlines() if line.strip()]
    if not lines:
        return ""

    trimmed = lines[:max_lines]
    rendered = "\n".join(f"  - {line}" for line in trimmed)
    omitted = len(lines) - len(trimmed)
    if omitted > 0:
        rendered = f"{rendered}\n  - [truncated {omitted} lines]"
    return rendered


# Regex to extract test location from traceback lines like:
#   File ".../test/test_utils.py", line 1076, in test_match_str
_TEST_TRACEBACK_RE = re.compile(
    r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(test_\w+)'
)
# Regex to extract the missing symbol from import-time errors like:
#   ImportError: cannot import name 'fix_xml_ampersands'
_IMPORT_ERROR_SYMBOL_RE = re.compile(
    r"ImportError: cannot import name ['\"]([^'\"]+)['\"]"
)
# Generic file reference in any traceback line
_TRACEBACK_FILE_RE = re.compile(r'File\s+"([^"]+)",\s+line\s+\d+')


def _extract_failing_test_function(*, test_output: str, repo_root: Path) -> str:
    """Extract the full failing test function from the repository.

    Strategy 1: traceback names a test_ function directly — resolve the file and
    extract that function.
    Strategy 2: import-time failure — parse the missing symbol name and search
    the referenced test files for a function that exercises it.
    """
    # Strategy 1: normal traceback with an explicit test_ function name
    match = _TEST_TRACEBACK_RE.search(test_output)
    if match:
        candidate = _resolve_path_under_root(match.group(1), repo_root)
        if candidate is not None:
            result = _extract_named_function(candidate, match.group(3), repo_root)
            if result:
                return result

    # Strategy 2: import-time error — find a test that exercises the missing symbol
    symbol_match = _IMPORT_ERROR_SYMBOL_RE.search(test_output)
    if not symbol_match:
        return ""
    symbol = symbol_match.group(1)
    for file_match in _TRACEBACK_FILE_RE.finditer(test_output):
        candidate = _resolve_path_under_root(file_match.group(1), repo_root)
        if candidate is None or not candidate.exists():
            continue
        result = _find_test_function_using(candidate, symbol, repo_root)
        if result:
            return result
    return ""


def _resolve_path_under_root(raw_path: str, repo_root: Path) -> Path | None:
    test_path = Path(raw_path)
    if not test_path.is_absolute():
        return repo_root / test_path
    if str(test_path).startswith(str(repo_root)):
        return test_path
    # heuristic: drop leading path components until we find a match under repo_root
    parts = list(test_path.parts)
    for i in range(len(parts)):
        possible = repo_root / Path(*parts[i:])
        if possible.exists():
            return possible
    return None


def _extract_named_function(candidate: Path, func_name: str, repo_root: Path) -> str:
    if not candidate.exists():
        return ""
    try:
        source = candidate.read_text(encoding="utf-8")
    except Exception:
        return ""
    start_idx = source.find(f"def {func_name}(")
    if start_idx == -1:
        return ""
    next_def = source.find("\ndef ", start_idx + 1)
    end_idx = next_def + 1 if next_def != -1 else len(source)
    return _format_test_function(source[start_idx:end_idx], func_name, candidate, repo_root)


def _find_test_function_using(candidate: Path, symbol: str, repo_root: Path) -> str:
    """Return the first test_ function in `candidate` whose body contains `symbol`."""
    try:
        source = candidate.read_text(encoding="utf-8")
    except Exception:
        return ""
    for func_match in re.finditer(r'^def (test_\w+)\(', source, re.MULTILINE):
        func_start = func_match.start()
        next_def = source.find("\ndef ", func_start + 1)
        end_idx = next_def + 1 if next_def != -1 else len(source)
        func_body = source[func_start:end_idx]
        if symbol in func_body:
            return _format_test_function(func_body, func_match.group(1), candidate, repo_root)
    return ""


def _format_test_function(func_source: str, func_name: str, file_path: Path, repo_root: Path) -> str:
    lines = func_source.splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    text = "\n".join(lines)
    if len(text) > 3000:
        text = text[:3000] + "\n... [truncated]"
    return (
        "\n\n--- Failing test function (read this ENTIRE function to understand all assertions) ---\n"
        f"File: {file_path.relative_to(repo_root)}\n"
        f"Function: {func_name}\n"
        "```python\n"
        f"{text}\n"
        "```\n"
        "--- End of test function ---"
    )
