from __future__ import annotations

from dataclasses import dataclass

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
        return snapshot_repo_state(cfg.repo_root)

    def ensure_temp_branch_for_first_iteration(self, *, cfg: RunConfig, iteration: int, logs: list[str]) -> None:
        if iteration != 1 or cfg.temp_branch is not None or not is_git_repository(cfg.repo_root):
            return

        cfg.temp_branch = create_temp_branch(
            cfg.repo_root,
            run_id=cfg.run_id,
            branch_prefix=resolve_temp_branch_prefix(cfg.run_input_metadata),
        )
        logs.extend(
            [
                f"git_original_branch={cfg.temp_branch.original_branch}",
                f"git_temp_branch={cfg.temp_branch.branch_name}",
            ]
        )

    def inspect_changes(self, *, cfg: RunConfig, before_snapshot: dict[str, str]) -> WorkspaceChangeSet:
        after_snapshot = snapshot_repo_state(cfg.repo_root)
        return detect_workspace_change_set(
            repo_root=cfg.repo_root,
            before=before_snapshot,
            after=after_snapshot,
        )

    def restore_temp_branch_for_debug(self, *, cfg: RunConfig, logs: list[str]) -> None:
        if cfg.temp_branch is None:
            return
        try:
            restore_original_branch(cfg.repo_root, original_branch=cfg.temp_branch.original_branch)
            logs.append(f"git_branch_cleanup=kept_for_debug:{cfg.temp_branch.branch_name}")
        except RuntimeError:
            pass

    def cleanup_temp_branch_after_success(self, cfg: RunConfig) -> str | None:
        if cfg.temp_branch is None:
            return None

        try:
            restore_original_branch(cfg.repo_root, original_branch=cfg.temp_branch.original_branch)
            delete_branch(cfg.repo_root, branch_name=cfg.temp_branch.branch_name)
        except RuntimeError as exc:
            return str(exc)
        return None
