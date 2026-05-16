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

# ── Handoff protocol ──────────────────────────────────────────────────────────

HANDOFF_PAYLOAD_FORMAT = (
    "Handoff payload format (must be valid JSON, no extra keys):\n"
    '{"summary":"...","evidence":["..."],"suspected_files":["..."],"next_focus":"...","confidence":0.75}\n'
    "Rules: use double quotes, no trailing commas, keep strings single-line (no newlines)."
)

