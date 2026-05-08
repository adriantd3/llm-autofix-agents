from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path

from llm_autofix_agents.flow.errors import WorkspaceError
from llm_autofix_agents.flow.runtime.options import resolve_temp_branch_prefix
from llm_autofix_agents.flow.workspace import git as _git
from llm_autofix_agents.flow.workspace import state as _state
from llm_autofix_agents.flow.workspace.git import TempBranchContext


@dataclass(frozen=True)
class WorkspaceManager:
    """High-level workspace operations used by the application flow."""

    def snapshot(self, repo_root: Path) -> dict[str, str]:
        try:
            return _state.snapshot_repo_state(repo_root)
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceError(f"workspace snapshot failed: {exc}") from exc

    def ensure_temp_branch(
        self,
        *,
        repo_root: Path,
        run_id: str,
        run_input_metadata: dict,
        iteration: int,
        current_branch: TempBranchContext | None,
        logs: list[str],
    ) -> TempBranchContext | None:
        """Create a temporary git branch for the first iteration if needed.

        Returns the new TempBranchContext, or None if no branch was created.
        The caller is responsible for storing the result in RunState.
        """
        try:
            is_repo = _git.is_git_repository(repo_root)
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceError(f"failed to detect git repository: {exc}") from exc

        if iteration != 1 or current_branch is not None or not is_repo:
            return None

        try:
            branch = _git.create_temp_branch(
                repo_root,
                run_id=run_id,
                branch_prefix=resolve_temp_branch_prefix(run_input_metadata),
            )
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceError(f"failed to create temporary branch: {exc}") from exc

        logs.extend(
            [
                f"git_original_branch={branch.original_branch}",
                f"git_temp_branch={branch.branch_name}",
            ]
        )
        return branch

    def inspect_changes(self, *, repo_root: Path, before_snapshot: dict[str, str]):
        try:
            after_snapshot = _state.snapshot_repo_state(repo_root)
            return _state.detect_workspace_change_set(
                repo_root=repo_root,
                before=before_snapshot,
                after=after_snapshot,
            )
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceError(f"failed to inspect workspace changes: {exc}") from exc

    def restore_all_changes(self, *, repo_root: Path, logs: list[str]) -> None:
        try:
            if _git._is_project_repo(repo_root) and not os.environ.get("AUTOFIX_ALLOW_RESTORE"):
                raise RuntimeError(
                    f"Blocked restore_all_changes in project repository: {repo_root}. "
                    "Use an isolated workspace or set AUTOFIX_ALLOW_RESTORE=1 (only in sandboxed environments)."
                )
            _git.restore_all_changes(repo_root)
            logs.append("workspace_restored_after_retryable_validation")
        except Exception as exc:  # noqa: BLE001
            logs.append(f"workspace_restore_error={exc}")
            raise WorkspaceError(f"failed to restore workspace after retryable validation: {exc}") from exc

    def restore_temp_branch_for_debug(
        self,
        *,
        repo_root: Path,
        temp_branch: TempBranchContext | None,
        logs: list[str],
    ) -> None:
        if temp_branch is None:
            return
        try:
            _git.restore_original_branch(repo_root, original_branch=temp_branch.original_branch)
            logs.append(f"git_branch_cleanup=kept_for_debug:{temp_branch.branch_name}")
        except Exception as exc:  # noqa: BLE001
            logging.getLogger(__name__).warning(
                "Failed to restore branch after debug: %s", exc
            )
            logs.append(f"git_branch_cleanup_error={exc}")

    def cleanup_temp_branch_after_success(
        self,
        *,
        repo_root: Path,
        temp_branch: TempBranchContext | None,
    ) -> str | None:
        if temp_branch is None:
            return None

        try:
            _git.restore_original_branch(repo_root, original_branch=temp_branch.original_branch)
            _git.delete_branch(repo_root, branch_name=temp_branch.branch_name)
        except Exception as exc:  # noqa: BLE001
            wrapped = WorkspaceError(f"failed to cleanup temporary branch: {exc}")
            return str(wrapped)
        return None

