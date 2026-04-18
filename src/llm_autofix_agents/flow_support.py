"""Compatibility shim for legacy imports.

Flow responsibilities were split into atomic modules under llm_autofix_agents.flow.
Keep this module as a thin re-export layer to avoid breaking existing imports.
"""

from llm_autofix_agents.flow import (
    PatchApplyResult,
    TestExecution,
    apply_unified_diff,
    build_iteration_input,
    build_test_signature,
    can_complete_early,
    collect_repo_diff,
    detect_changed_files,
    extract_int,
    is_no_progress,
    is_regression,
    resolve_repo_root,
    resolve_test_timeout_seconds,
    run_git_apply,
    run_test_command,
    snapshot_repo_state,
    sum_counts,
    to_test_results,
)

__all__ = [
    "PatchApplyResult",
    "TestExecution",
    "apply_unified_diff",
    "build_iteration_input",
    "build_test_signature",
    "can_complete_early",
    "collect_repo_diff",
    "detect_changed_files",
    "extract_int",
    "is_no_progress",
    "is_regression",
    "resolve_repo_root",
    "resolve_test_timeout_seconds",
    "run_git_apply",
    "run_test_command",
    "snapshot_repo_state",
    "sum_counts",
    "to_test_results",
]
