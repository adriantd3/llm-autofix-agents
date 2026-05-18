"""Shared instruction constants for all APR agent architectures.

Each constant has a single canonical owner here. Import and embed in individual
prompt modules via f-strings — do not copy text across files.
"""
from __future__ import annotations

# ── Role boundaries ───────────────────────────────────────────────────────────

TEST_FILES_ARE_CORRECT_RULE = (
    "NEVER modify test files. The failing tests are CORRECT. The bug is always in the source code.\n"
    "If you modify ANY file under test/ or tests/, or any file named test_*.py or *_test.py,\n"
    "your iteration is REJECTED and the run ENDS."
)

# ── Diagnosis principles ──────────────────────────────────────────────────────

CODE_FIRST_DIAGNOSIS_PRINCIPLE = (
    "Read the source function under test BEFORE analyzing test assertions.\n"
    "The failing test is evidence of where the bug manifests, not the specification of what to fix.\n"
    "The source code tells you the correct behavior; the test tells you the symptom."
)

# ── Patch discipline ──────────────────────────────────────────────────────────

TOOL_EXECUTION_RULE = (
    "Writing a fix in your reasoning or plan does NOT apply it to the repository.\n"
    "You MUST call replace_in_file (or replace_lines) to apply every change.\n"
    "If you described a fix but did not call the tool, the codebase is unchanged."
)

REPLACE_NOT_WRITE_RULE = (
    "Use replace_in_file for files that already exist.\n"
    "replace_in_file makes targeted edits without destroying surrounding content.\n"
    "write_file overwrites the entire file — only use it to create files that do not exist yet."
)

PROPAGATION_CHECK_RULE = (
    "After applying a fix, ask: does this change need to propagate? If you modified a function\n"
    "signature, added a new exception, or changed a parameter, search for callers and related\n"
    "files that must be updated consistently. A fix that only touches one side of an interface\n"
    "is incomplete."
)

READ_BEFORE_EDIT_RULE = (
    "Never edit a file you have not read in this iteration. "
    "Always call read_file before replace_in_file / replace_lines / write_file."
)

WINDOWED_READ_RULE = (
    "read_file: always specify start_line/end_line — target 40–80 line windows. "
    "Use the returned line_count to paginate large files. "
    "Never read an entire large file in one call, and never re-read the same range twice."
)

# The `env/` virtualenv is pre-built by the benchmarking Docker infrastructure.
# System pip belongs to a different Python and its installs will not be visible to the test runner.
# Agents that recreate the venv with `python -m venv env` break it entirely.
VENV_ENV_DIR_RULE = (
    "The `env/` directory is a pre-compiled Python virtualenv managed by the benchmarking "
    "infrastructure. NEVER recreate it with `python -m venv env` — that breaks the environment. "
    "If a test fails because a Python package is missing, install it with `env/bin/pip install "
    "<package>` — NOT the system `pip`, which writes to a different Python and has no effect on "
    "the test runner. Do not list, search, or read files inside `env/`."
)

# ── Handoff protocol ──────────────────────────────────────────────────────────

HANDOFF_PAYLOAD_FORMAT = (
    "Handoff payload format (must be valid JSON, no extra keys):\n"
    '{"summary":"...","evidence":["..."],"suspected_files":["..."],"next_focus":"...","confidence":0.75}\n'
    "Rules: use double quotes, no trailing commas, keep strings single-line (no newlines)."
)

