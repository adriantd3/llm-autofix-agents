from __future__ import annotations

from typing import Any


def resolve_max_iterations(metadata: dict[str, Any]) -> int:
    value = metadata.get("max_iterations")
    if value is None:
        return 3
    if not isinstance(value, int) or value < 1 or value > 6:
        raise ValueError("metadata.max_iterations must be 1-6")
    return value


def resolve_tool_profile(metadata: dict[str, Any]) -> str:
    value = metadata.get("tool_profile")
    if value is None:
        return "full"
    if not isinstance(value, str):
        raise ValueError("metadata.tool_profile must be minimal/core/full")
    normalized = value.strip().lower()
    if normalized not in {"minimal", "core", "full"}:
        raise ValueError("metadata.tool_profile must be minimal/core/full")
    return normalized


def resolve_temp_branch_prefix(metadata: dict[str, Any]) -> str:
    value = metadata.get("temp_branch_prefix")
    if value is None:
        return "autofix"
    if not isinstance(value, str):
        raise ValueError("metadata.temp_branch_prefix must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError("metadata.temp_branch_prefix cannot be empty")
    return normalized


def metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str):
        return value.strip() or None
    return None
