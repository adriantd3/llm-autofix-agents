from __future__ import annotations

from typing import Any

from llm_autofix_agents.contracts import RunArchitecture


def resolve_architecture(metadata: dict[str, Any], explicit: str | None = None) -> str:
    value = explicit
    if value is None:
        value = metadata.get("runtime_architecture")
    if value is None:
        return RunArchitecture.MONO_AGENT.value
    if not isinstance(value, str):
        raise ValueError("runtime_architecture must be a string")
    normalized = value.strip().lower()
    if normalized in {strategy.value for strategy in RunArchitecture}:
        return normalized
    raise ValueError(f"Unsupported architecture strategy: {value}")


def resolve_max_iterations(metadata: dict[str, Any]) -> int:
    value = metadata.get("max_iterations")
    if value is None:
        return 3
    if not isinstance(value, int) or value < 1 or value > 6:
        raise ValueError("metadata.max_iterations must be 1-6")
    return value


def resolve_max_turns(metadata: dict[str, Any]) -> int:
    value = metadata.get("max_turns")
    if value is None:
        return 3
    if not isinstance(value, int) or value < 1 or value > 50:
        raise ValueError("metadata.max_turns must be 1-50")
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


def resolve_agent_models(metadata: dict[str, Any]) -> dict[str, str]:
    value = metadata.get("runtime_agent_models")
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("metadata.runtime_agent_models must be a dict of role->model")

    normalized: dict[str, str] = {}
    for role, model in value.items():
        if not isinstance(role, str) or not isinstance(model, str):
            raise ValueError("metadata.runtime_agent_models must contain string role->model")
        role_name = role.strip().lower()
        model_name = model.strip()
        if not role_name or not model_name:
            raise ValueError("metadata.runtime_agent_models cannot contain empty role or model")
        normalized[role_name] = model_name

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


def resolve_iteration_timeout_seconds(metadata: dict[str, Any]) -> int | None:
    value = metadata.get("iteration_timeout_seconds")
    if value is None:
        return None
    if not isinstance(value, int) or value < 30 or value > 3600:
        raise ValueError("metadata.iteration_timeout_seconds must be an integer between 30 and 3600")
    return value


def metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str):
        return value.strip() or None
    return None
