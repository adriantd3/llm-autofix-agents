from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


@dataclass(frozen=True)
class TempBranchContext:
    branch_name: str
    original_branch: str


def is_git_repository(repo_root: Path) -> bool:
    result = _run_git(repo_root, ["rev-parse", "--is-inside-work-tree"])
    return result.returncode == 0 and result.stdout.strip().lower() == "true"


def current_branch(repo_root: Path) -> str:
    result = _run_git(repo_root, ["rev-parse", "--abbrev-ref", "HEAD"])
    if result.returncode != 0:
        raise RuntimeError("Unable to detect current git branch")
    branch = result.stdout.strip()
    if not branch:
        raise RuntimeError("Unable to detect current git branch")
    return branch


def create_temp_branch(
    repo_root: Path,
    *,
    run_id: str,
    branch_prefix: str = "autofix",
    now: datetime | None = None,
) -> TempBranchContext:
    original_branch = current_branch(repo_root)
    branch_name = build_temp_branch_name(run_id=run_id, branch_prefix=branch_prefix, now=now)
    create_result = _run_git(repo_root, ["switch", "-c", branch_name])
    if create_result.returncode != 0:
        raise RuntimeError(
            f"Failed to create temporary branch '{branch_name}': {create_result.stderr.strip() or 'unknown error'}"
        )
    return TempBranchContext(branch_name=branch_name, original_branch=original_branch)


def restore_original_branch(repo_root: Path, *, original_branch: str) -> None:
    restore_result = _run_git(repo_root, ["switch", original_branch])
    if restore_result.returncode != 0:
        raise RuntimeError(
            f"Failed to restore original branch '{original_branch}': {restore_result.stderr.strip() or 'unknown error'}"
        )


def delete_branch(repo_root: Path, *, branch_name: str) -> None:
    delete_result = _run_git(repo_root, ["branch", "-D", branch_name])
    if delete_result.returncode != 0:
        raise RuntimeError(
            f"Failed to delete temporary branch '{branch_name}': {delete_result.stderr.strip() or 'unknown error'}"
        )


def build_temp_branch_name(
    *,
    run_id: str,
    branch_prefix: str,
    now: datetime | None = None,
) -> str:
    safe_prefix = _sanitize_branch_component(branch_prefix) or "autofix"
    timestamp = (now if now is not None else datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    safe_run_id = _sanitize_branch_component(run_id)
    return f"{safe_prefix}/{timestamp}-{safe_run_id}"


def _sanitize_branch_component(value: str) -> str:
    sanitized = value.strip().replace(" ", "-")
    allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_/"
    return "".join(ch for ch in sanitized if ch in allowed).strip("/-")


def _run_git(repo_root: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=False,
    )
