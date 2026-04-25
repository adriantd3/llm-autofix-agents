from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.flow.errors import WorkspaceError
from llm_autofix_agents.flow.models import WorkspaceChangeSet
from llm_autofix_agents.flow.runtime.context import RunConfig
from llm_autofix_agents.flow.runtime.options import resolve_temp_branch_prefix
from llm_autofix_agents.flow.workspace.git import (
    create_temp_branch,
    delete_branch,
    is_git_repository,
    restore_original_branch,
)
from llm_autofix_agents.flow.workspace.state import detect_workspace_change_set, snapshot_repo_state


@dataclass(frozen=True)
class WorkspaceManager:
    """High-level workspace operations used by the application flow."""

    def snapshot(self, cfg: RunConfig) -> dict[str, str]:
        try:
            return snapshot_repo_state(cfg.repo_root)
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceError(f"workspace snapshot failed: {exc}") from exc

    def ensure_temp_branch_for_first_iteration(self, *, cfg: RunConfig, iteration: int, logs: list[str]) -> None:
        try:
            is_repo = is_git_repository(cfg.repo_root)
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceError(f"failed to detect git repository: {exc}") from exc

        if iteration != 1 or cfg.temp_branch is not None or not is_repo:
            return

        try:
            cfg.temp_branch = create_temp_branch(
                cfg.repo_root,
                run_id=cfg.run_id,
                branch_prefix=resolve_temp_branch_prefix(cfg.run_input_metadata),
            )
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceError(f"failed to create temporary branch: {exc}") from exc

        logs.extend(
            [
                f"git_original_branch={cfg.temp_branch.original_branch}",
                f"git_temp_branch={cfg.temp_branch.branch_name}",
            ]
        )

    def inspect_changes(self, *, cfg: RunConfig, before_snapshot: dict[str, str]) -> WorkspaceChangeSet:
        try:
            after_snapshot = snapshot_repo_state(cfg.repo_root)
            return detect_workspace_change_set(
                repo_root=cfg.repo_root,
                before=before_snapshot,
                after=after_snapshot,
            )
        except Exception as exc:  # noqa: BLE001
            raise WorkspaceError(f"failed to inspect workspace changes: {exc}") from exc

    def restore_temp_branch_for_debug(self, *, cfg: RunConfig, logs: list[str]) -> None:
        if cfg.temp_branch is None:
            return
        try:
            restore_original_branch(cfg.repo_root, original_branch=cfg.temp_branch.original_branch)
            logs.append(f"git_branch_cleanup=kept_for_debug:{cfg.temp_branch.branch_name}")
        except Exception as exc:  # noqa: BLE001
            logs.append(f"git_branch_cleanup_error={exc}")
            pass

    def cleanup_temp_branch_after_success(self, cfg: RunConfig) -> str | None:
        if cfg.temp_branch is None:
            return None

        try:
            restore_original_branch(cfg.repo_root, original_branch=cfg.temp_branch.original_branch)
            delete_branch(cfg.repo_root, branch_name=cfg.temp_branch.branch_name)
        except Exception as exc:  # noqa: BLE001
            wrapped = WorkspaceError(f"failed to cleanup temporary branch: {exc}")
            return str(wrapped)
        return None
