from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TestExecution:
    exit_code: int
    timed_out: bool
    output: str
    signature: str


@dataclass(frozen=True)
class PatchApplyResult:
    applied: bool
    reason: str


@dataclass(frozen=True)
class WorkspaceChangeSet:
    """Authoritative repository changes observed by the runtime."""

    modified_files: list[str]
    added_files: list[str]
    deleted_files: list[str]
    untracked_files: list[str]
    diff: str
    diff_complete: bool

    @property
    def tracked_changed_files(self) -> list[str]:
        return sorted({*self.modified_files, *self.added_files, *self.deleted_files})

    @property
    def all_changed_files(self) -> list[str]:
        return sorted({*self.tracked_changed_files, *self.untracked_files})

    @property
    def repo_changed(self) -> bool:
        return bool(self.all_changed_files)
