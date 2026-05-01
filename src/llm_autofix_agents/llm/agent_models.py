from __future__ import annotations

from collections.abc import Mapping


def resolve_agent_model(
    agent_models: Mapping[str, str] | None,
    *,
    role: str,
    default_model: str,
) -> str:
    if not agent_models:
        return default_model

    normalized_models: dict[str, str] = {}
    for raw_role, raw_model in agent_models.items():
        if not isinstance(raw_role, str) or not isinstance(raw_model, str):
            continue
        role_name = raw_role.strip().lower()
        model_name = raw_model.strip()
        if not role_name or not model_name:
            continue
        normalized_models[role_name] = model_name

    normalized_role = role.strip().lower()
    if normalized_role:
        model = normalized_models.get(normalized_role)
        if model:
            return model

    main_model = normalized_models.get("main")
    if main_model:
        return main_model

    return default_model
