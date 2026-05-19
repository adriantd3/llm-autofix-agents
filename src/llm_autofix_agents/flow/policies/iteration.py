from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

_SNAPSHOT_SIGNATURE_RE = re.compile(r"-\s+signature:\s+([a-f0-9]+)")

from llm_autofix_agents.flow.models import TestExecution, WorkspaceChangeSet

# An "in_progress" status at iteration boundary means the agent was cut off by max_turns
# rather than finishing cleanly — it never set status="done" or "stuck".
_IN_PROGRESS_STATUS = "in_progress"
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.tools.text import compact_test_output

_FAILURE_DRIVEN_INTRO = (
    "You are an autonomous software repair agent with a LIMITED number of turns. "
    "Analyze the failing test results below, find the root cause in the repository, "
    "apply the smallest correct change, rerun the focused test command, inspect the "
    "final diff, and then report the final status. "
    "NEVER modify test files — all failures are source-code bugs. "
    "Do NOT re-run the failing test before making code changes."
)
_MAX_BASELINE_OUTPUT_CHARS = 4000
_MAX_SNAPSHOT_OUTPUT_CHARS = 2000


_VALIDATION_FEEDBACK_TEMPLATE = (
    "⚠ VALIDATION REJECTION FROM PREVIOUS ITERATION:\n"
    "{feedback}\n\n"
    "Your changes from the previous iteration have been reverted. "
    "DO NOT repeat the same mistake.\n\n"
)

_NO_EDIT_SNAPSHOT_SIGNAL = "No source files were modified"
_ASSERTIVE_NO_EDIT_TASK = (
    "Task:\n"
    "You MUST apply a code change this iteration. "
    "The previous attempt made no edits — do not repeat that. "
    "Read the failing test, locate the source file, and call replace_in_file before running tests."
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
    latest_test_execution: TestExecution | None = None,
    previous_proposal_status: str | None = None,
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

    # Remind the agent of the original failure only on the first continuation (iteration 2).
    # By iteration 3+ the agent has already seen it twice — repeating it is pure noise.
    baseline_reminder = ""
    if iteration == 2 and baseline_test_execution and baseline_test_execution.exit_code != 0:
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
            f"\n\nFocused test command (pass to your test validation tool):\n"
            f"{test_command.strip()}\n"
        )

    anti_wander = (
        f"This is attempt {iteration}/{max_iterations}. Your previous attempt did not complete the repair. "
        "If your plan for this attempt is the same as before, stop now and report status='stuck'. "
        "Otherwise, your first action must be different from what you tried last time.\n\n"
    )

    no_edit_previous = latest_snapshot is not None and _NO_EDIT_SNAPSHOT_SIGNAL in latest_snapshot

    # Workspace tree — only inject in recovery (no-edit) iterations for re-localization.
    # On normal continuation passes the agent already knows the layout; repeating it wastes tokens.
    workspace_tree_block = ""
    if no_edit_previous and repo_root is not None:
        workspace_tree_block = _build_workspace_tree(repo_root)

    # When the previous iteration made no edits, attempt to re-localize: re-extract
    # the source function from the latest test output and inject it as a concrete
    # starting point. This reuses the same localization machinery as iteration 1.
    recovery_source_block = ""
    if no_edit_previous and repo_root is not None and latest_test_execution is not None:
        recovery_source_block = _extract_source_function_under_test(
            test_output=latest_test_execution.output,
            repo_root=repo_root,
        )

    task_block = _build_task_block(
        no_edit_previous=no_edit_previous,
        previous_proposal_status=previous_proposal_status,
        has_recovery_source=bool(recovery_source_block),
    )

    return (
        f"{feedback_prefix}"
        f"{anti_wander}"
        f"[ITERATION {iteration}/{max_iterations}]\n"
        f"{task_block}\n\n"
        f"Previous attempt summary (agent-reported):\n{previous_message}"
        f"{snapshot_block}"
        f"{test_command_reminder}"
        f"{recovery_source_block}\n\n"
        f"{baseline_reminder}"
        f"{workspace_tree_block}"
    )


def build_continuation_snapshot(
    *,
    proposal: AgentFixIterationRecord,
    changes: WorkspaceChangeSet,
    test_execution: TestExecution,
    repo_root: Path | None = None,
    previous_test_signature: str | None = None,
) -> str:
    compact_output = compact_test_output(test_execution.output, max_chars=_MAX_SNAPSHOT_OUTPUT_CHARS)
    output_block = _indent_block(compact_output or "(no output)", prefix="    ")

    changed_files = changes.all_changed_files
    if changed_files:
        changed_block = "\n".join(f"  - {path}" for path in changed_files)
    else:
        changed_block = "  - (none)"

    notes_block = _format_notes_block(proposal.proposal.notes)

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
            "You MUST apply at least one code change before validating. "
            "Investigate the root cause and edit the relevant source file."
        )
    # Signal when the test failure is unchanged — the edit had no effect on the failing path.
    if (
        previous_test_signature is not None
        and test_execution.exit_code != 0
        and test_execution.signature == previous_test_signature
    ):
        lines.append(
            "⚠ ERROR UNCHANGED: The test failure signature is identical to the previous iteration. "
            "Your edit had no effect on the failing code path.\n"
            "  • If you modified the right file, the fix logic is incorrect — try a different approach.\n"
            "  • If you haven't located the failing code path yet, search more broadly."
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


_EXIT4_GUIDANCE = (
    "\n\n⚠ EXIT CODE 4 — TEST COLLECTION FAILURE: pytest could not import or collect tests.\n"
    "This is almost always a missing or incompatible dependency. Look for "
    "ModuleNotFoundError or ImportError in the output above.\n"
    "- To fix a missing package: use `env/bin/pip install <package>` via execute_command.\n"
    "- Do NOT modify test files to work around missing imports.\n"
    "- Check <bugsinpy_requirements> below for the expected package list."
)
_MAX_REQUIREMENTS_CHARS = 1500


def _build_exit4_block(exit_code: int, repo_root: Path | None) -> str:
    """Return exit-4 guidance + requirements file content block, or empty string."""
    if exit_code != 4:
        return ""
    requirements_block = ""
    if repo_root is not None:
        req_path = repo_root / "bugsinpy_requirements.txt"
        if req_path.is_file():
            try:
                content = req_path.read_text(encoding="utf-8")
                if len(content) > _MAX_REQUIREMENTS_CHARS:
                    content = content[:_MAX_REQUIREMENTS_CHARS] + "\n... [truncated]"
                requirements_block = f"\n\n<bugsinpy_requirements>\n{content.strip()}\n</bugsinpy_requirements>"
            except OSError:
                pass
    return _EXIT4_GUIDANCE + requirements_block


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

    source_function_block = ""
    test_function_block = ""
    workspace_tree_block = ""
    if repo_root is not None:
        workspace_tree_block = _build_workspace_tree(repo_root)
        # Source function is injected BEFORE the test function so the model reads
        # the semantic contract first — leveraging position bias (models attend more
        # to content that appears early in the prompt, Liu et al. "Lost in the Middle" 2023).
        source_function_block = _extract_source_function_under_test(
            test_output=baseline_test_execution.output,
            repo_root=repo_root,
        )
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
        f"{_build_exit4_block(baseline_test_execution.exit_code, repo_root)}"
        f"{workspace_tree_block}"
        f"{source_function_block}"
        f"{test_function_block}"
    )


def extract_snapshot_test_signature(snapshot: str | None) -> str | None:
    """Parse the test signature hash from a continuation snapshot string."""
    if not snapshot:
        return None
    m = _SNAPSHOT_SIGNATURE_RE.search(snapshot)
    return m.group(1) if m else None


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
    p = proposal.proposal
    status = p.status.strip().lower()
    reasoning_summary = _normalize(p.reasoning_summary)
    notes = _normalize(p.notes or "")
    return f"status={status}|reasoning_summary={reasoning_summary}|notes={notes}"


def _build_task_block(
    *,
    no_edit_previous: bool,
    previous_proposal_status: str | None,
    has_recovery_source: bool,
) -> str:
    """Return the task directive for a continuation iteration.

    Three cases:
    - No prior no-edit: standard "continue improving" directive.
    - 0 edits + agent was cut off by max_turns (in_progress status): re-localization recovery.
    - 0 edits + agent chose to stop (stuck/done): assertive "you must edit" directive.
    """
    if not no_edit_previous:
        return (
            "Task:\n"
            "Continue improving the repair strategy. Use tools to inspect and edit, "
            "then validate with the test command.\n"
            "IMPORTANT: If your last fix broke a different assertion, you need a fix "
            "that satisfies ALL constraints simultaneously."
        )

    was_cut_off = (
        previous_proposal_status is not None
        and previous_proposal_status.strip().lower() == _IN_PROGRESS_STATUS
    )

    if was_cut_off and has_recovery_source:
        return (
            "Task:\n"
            "The previous iteration exhausted all its turns without making any edit — "
            "the search went in the wrong direction.\n"
            "The source function shown above is extracted directly from the failing traceback. "
            "Start by reading it. Identify the exact line that is wrong. "
            "Call replace_in_file to apply the fix. Do NOT begin with broad searches — "
            "you already have the target function above."
        )

    if was_cut_off:
        return (
            "Task:\n"
            "The previous iteration exhausted all its turns without making any edit. "
            "You MUST apply a code change this iteration. "
            "Use the traceback in the snapshot to find the source file, read the relevant lines, "
            "then call replace_in_file. Do not spend more than 3 tool calls on discovery."
        )

    # Agent chose to stop (stuck or no hypothesis) without editing
    if has_recovery_source:
        return (
            "Task:\n"
            "You MUST apply a code change this iteration. "
            "The source function shown above is your starting point — read it, fix it, validate it. "
            "Do NOT start with broad searches."
        )

    return _ASSERTIVE_NO_EDIT_TASK


def _normalize(text: str) -> str:
    return " ".join(text.split()).strip().lower()


def _indent_block(text: str, *, prefix: str) -> str:
    return "\n".join(f"{prefix}{line}" for line in text.splitlines())


def _format_notes_block(notes: str | None, *, max_lines: int = 4) -> str:
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


_WORKSPACE_TREE_EXCLUDE = frozenset({
    "env", "venv", ".venv", ".git", "__pycache__", ".pytest_cache",
    "node_modules", ".tox", ".mypy_cache", "htmlcov", "dist", "build",
})
_MAX_FILES_PER_DIR = 8
_MAX_TREE_DIRS = 12


def _build_workspace_tree(repo_root: Path) -> str:
    """Return a compact workspace layout string for injection into the first iteration prompt."""
    lines = ["Workspace layout (use these path prefixes for search_files and read_file):"]
    large_excluded: list[str] = []
    root_py_files: list[str] = []
    dir_rows: list[str] = []
    shown_dirs = 0

    for entry in sorted(repo_root.iterdir()):
        if entry.name in _WORKSPACE_TREE_EXCLUDE:
            if entry.is_dir():
                count = sum(1 for _ in entry.rglob("*") if _.is_file())
                if count > 20:
                    large_excluded.append(f"  {entry.name}/  ({count}+ files — do NOT search here)")
            continue
        if entry.is_file() and entry.suffix == ".py":
            root_py_files.append(entry.name)
            continue
        if not entry.is_dir():
            continue
        if shown_dirs >= _MAX_TREE_DIRS:
            continue

        # Direct .py files in this directory
        direct_py = sorted(p.name for p in entry.iterdir() if p.is_file() and p.suffix == ".py")
        # Non-excluded subdirectories that contain .py files
        sub_dirs = sorted(
            sub.name
            for sub in entry.iterdir()
            if sub.is_dir()
            and sub.name not in _WORKSPACE_TREE_EXCLUDE
            and any(True for _ in sub.rglob("*.py"))
        )
        if not direct_py and not sub_dirs:
            continue

        parts: list[str] = []
        if direct_py:
            preview = ", ".join(direct_py[:_MAX_FILES_PER_DIR])
            if len(direct_py) > _MAX_FILES_PER_DIR:
                preview += f", ... ({len(direct_py)} total)"
            parts.append(preview)
        if sub_dirs:
            parts.append("subdirs: " + ", ".join(f"{s}/" for s in sub_dirs[:5]))
        dir_rows.append(f"  {entry.name}/  →  " + "  |  ".join(parts))
        shown_dirs += 1

    if not dir_rows and not large_excluded and not root_py_files:
        return ""

    lines.extend(dir_rows)
    if root_py_files:
        lines.append(f"  (root)  →  {', '.join(root_py_files)}")
    lines.extend(large_excluded)

    return "\n\n<workspace_layout>\n" + "\n".join(lines) + "\n</workspace_layout>"


# Regex to extract test location from traceback lines like:
#   File ".../test/test_utils.py", line 1076, in test_match_str
_TEST_TRACEBACK_RE = re.compile(
    r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(test_\w+)'
)
# Pytest FAILED summary line: "FAILED tests/foo.py::Class::test_method"
# Captures the .py file path (group 1) and the last test_* component (group 2).
_PYTEST_FAILED_RE = re.compile(
    r'FAILED\s+([^\s:]+\.py)::(?:\w+::)*(test_\w+)'
)
# Regex to extract the missing symbol from import-time errors like:
#   ImportError: cannot import name 'fix_xml_ampersands'
_IMPORT_ERROR_SYMBOL_RE = re.compile(
    r"ImportError: cannot import name ['\"]([^'\"]+)['\"]"
)
# Generic file reference in any traceback line
_TRACEBACK_FILE_RE = re.compile(r'File\s+"([^"]+)",\s+line\s+\d+')
# All traceback frames: file + line + function name
_ALL_FRAMES_RE = re.compile(
    r'File\s+"([^"]+)",\s+line\s+(\d+),\s+in\s+(\w+)'
)


def _extract_failing_test_function(*, test_output: str, repo_root: Path) -> str:
    """Extract the full failing test function from the repository.

    Strategy 1: Python traceback names a test_ function directly — File "...", in test_func.
    Strategy 1b: pytest FAILED summary line — "FAILED path::Class::test_func".
    Strategy 2: import-time failure — parse the missing symbol and search test files.
    """
    # Strategy 1: normal Python traceback with an explicit test_ function name
    match = _TEST_TRACEBACK_RE.search(test_output)
    if match:
        candidate = _resolve_path_under_root(match.group(1), repo_root)
        if candidate is not None:
            result = _extract_named_function(candidate, match.group(3), repo_root)
            if result:
                return result

    # Strategy 1b: pytest assertion-style failure — no File/line/in frame for the test
    # function itself, but pytest always appends "FAILED path::Class::test_method".
    for m in _PYTEST_FAILED_RE.finditer(test_output):
        candidate = _resolve_path_under_root(m.group(1), repo_root)
        if candidate is not None:
            result = _extract_named_function(candidate, m.group(2), repo_root)
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
        suffix = Path(*parts[i:])
        if suffix.is_absolute():
            continue  # Path('/') + absolute discards repo_root; skip
        possible = repo_root / suffix
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
    # Match test functions at any indentation level (top-level and class methods).
    for func_match in re.finditer(r'^([ \t]*)def (test_\w+)\(', source, re.MULTILINE):
        indent = func_match.group(1)
        func_name = func_match.group(2)
        func_start = func_match.start()
        tail = source[func_start + 1:]
        # Next peer: same indentation def (sibling method or next top-level function)
        peer = re.search(r'\n' + re.escape(indent) + r'def ', tail)
        # If inside a class, also stop at next top-level def/class
        parent = re.search(r'\ndef |\nclass ', tail) if indent else None
        candidates = [m for m in (peer, parent) if m is not None]
        if candidates:
            end_idx = func_start + 1 + min(m.start() for m in candidates) + 1
        else:
            end_idx = len(source)
        func_body = source[func_start:end_idx]
        if symbol in func_body:
            return _format_test_function(func_body, func_name, candidate, repo_root)
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


_SYNTHETIC_FRAME_NAMES = frozenset({"<module>", "<lambda>", "<listcomp>", "<genexpr>", "<dictcomp>"})


def _is_test_path(raw_path: str) -> bool:
    lowered = raw_path.lower().replace("\\", "/")
    if "/test/" in lowered or "/tests/" in lowered:
        return True
    basename = lowered.rsplit("/", 1)[-1]
    stem = basename.rsplit(".", 1)[0] if "." in basename else basename
    return stem.startswith("test_") or stem.endswith("_test")


def _extract_raw_function(source: str, func_name: str) -> str | None:
    """Return the raw source text of `func_name` from `source`, or None."""
    start_idx = source.find(f"def {func_name}(")
    if start_idx == -1:
        return None
    next_def = source.find("\ndef ", start_idx + 1)
    end_idx = next_def + 1 if next_def != -1 else len(source)
    lines = source[start_idx:end_idx].splitlines()
    while lines and not lines[-1].strip():
        lines.pop()
    return "\n".join(lines)


def _format_source_function(func_source: str, func_name: str, file_path: Path, repo_root: Path) -> str:
    if len(func_source) > 3000:
        func_source = func_source[:3000] + "\n... [truncated]"
    return (
        "\n\n--- Source function under test (defines the CORRECT behavior — understand this BEFORE reading the test) ---\n"
        f"File: {file_path.relative_to(repo_root)}\n"
        f"Function: {func_name}\n"
        "```python\n"
        f"{func_source}\n"
        "```\n"
        "--- End of source function ---"
    )


def _extract_source_function_under_test(*, test_output: str, repo_root: Path) -> str:
    """Extract the innermost source function from the traceback.

    Walks all traceback frames from innermost (closest to the error) to outermost,
    skipping test files and synthetic frames, and returns the first source function
    that can be resolved under repo_root. Injected before the test function in the
    prompt so the model reads the semantic contract first (position bias mitigation).
    """
    frames = _ALL_FRAMES_RE.findall(test_output)
    for raw_path, _line_no, func_name in reversed(frames):
        if func_name in _SYNTHETIC_FRAME_NAMES:
            continue
        if _is_test_path(raw_path):
            continue
        candidate = _resolve_path_under_root(raw_path, repo_root)
        if candidate is None or not candidate.exists():
            continue
        try:
            candidate.relative_to(repo_root)
        except ValueError:
            continue
        try:
            source = candidate.read_text(encoding="utf-8")
        except Exception:
            continue
        raw = _extract_raw_function(source, func_name)
        if raw:
            return _format_source_function(raw, func_name, candidate, repo_root)
    return ""
