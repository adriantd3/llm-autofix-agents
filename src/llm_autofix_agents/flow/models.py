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

    changed_files: list[str]
    diff: str

    @property
    def repo_changed(self) -> bool:
        return bool(self.changed_files)
