"""Pre-test workspace validators.

Each validator checks that the workspace is in a valid state before running tests.
Validators are dataset-specific and injected into the orchestrator and iteration runner.
"""

from __future__ import annotations

from pathlib import Path

from llm_autofix_agents.contracts import RunInput
from llm_autofix_agents.datasets import bugsinpy as _bugsinpy
from llm_autofix_agents.flow.errors import WorkspaceError


def validate_bugsinpy_workspace(
    *,
    run_input: RunInput,
    repo_root: Path,
    logs: list[str],
    phase: str,
) -> None:
    """Validate BugsInPy workspace has required artifacts before tests.

    Raises WorkspaceError if required artifacts are missing.
    No-op for non-BugsInPy runs.
    """
    if not _bugsinpy.is_bugsinpy_metadata(run_input.metadata):
        return
    compile_required = _bugsinpy.compile_required_from_metadata(run_input.metadata)
    missing = _bugsinpy.missing_workspace_artifacts(repo_root, compile_required=compile_required)
    if not missing:
        return
    missing_str = ", ".join(missing)
    logs.append(f"bugsinpy_missing_files={missing_str}")
    raise WorkspaceError(
        f"BugsInPy workspace missing required artifacts before {phase} tests: {missing_str}"
    )
