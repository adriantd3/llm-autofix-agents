from __future__ import annotations

from llm_autofix_agents.flow.models import FileChangeTelemetrySet, WorkspaceChangeSet


def to_file_change_telemetry_set(changes: WorkspaceChangeSet) -> FileChangeTelemetrySet:
    """Convert a WorkspaceChangeSet into a categorized FileChangeTelemetrySet."""
    return FileChangeTelemetrySet(
        modified_files=list(changes.modified_files),
        added_files=list(changes.added_files),
        deleted_files=list(changes.deleted_files),
        untracked_files=list(changes.untracked_files),
    )
