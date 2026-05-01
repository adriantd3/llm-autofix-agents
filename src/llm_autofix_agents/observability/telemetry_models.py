from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FileChangeTelemetrySet:
    """Semantic file change set for telemetry."""

    modified_files: list[str]
    added_files: list[str]
    deleted_files: list[str]
    untracked_files: list[str]


@dataclass(frozen=True)
class IterationTelemetryResult:
    """Complete result for finishing an iteration."""

    started_at: str
    duration_seconds: float
    status: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    tool_calls_count: int
    changed_files_count: int
    repo_changed: bool
    test_exit_code: int
    test_timed_out: bool
    test_signature: str
