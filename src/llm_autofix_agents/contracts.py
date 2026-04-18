from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from os import environ as os_environ
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RunStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    PARTIAL = "partial"


class StopReason(StrEnum):
    COMPLETED = "completed"
    MAX_ITERATIONS = "max_iterations"
    NO_PROGRESS = "no_progress"
    TOOL_FAILURE = "tool_failure"
    INFRA_FAILURE = "infra_failure"
    VALIDATION_FAILURE = "validation_failure"


class ErrorCategory(StrEnum):
    TOOL = "tool"
    INFRA = "infra"
    MODEL = "model"
    VALIDATION = "validation"
    UNKNOWN = "unknown"


class RunInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    target_repo: str | None = None
    test_command: str | None = None

    @field_validator("prompt")
    @classmethod
    def _normalize_prompt(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("prompt cannot be empty")
        return normalized


class TestResults(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)

    @model_validator(mode="after")
    def _check_consistency(self) -> TestResults:
        if self.passed + self.failed > self.total:
            raise ValueError("passed + failed cannot be greater than total")
        return self


class RunError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: ErrorCategory
    message: str = Field(min_length=1)
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class RunIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1)
    run_fingerprint: str = Field(min_length=16, max_length=16)
    iteration: int = Field(ge=1)
    iteration_id: str = Field(min_length=1)


class ContainerInstantiation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository: str = Field(min_length=1)
    branch: str = Field(min_length=1)
    architecture: str = Field(min_length=1)
    agent_models: dict[str, str] = Field(min_length=1)
    bootstrap_prompt: str = Field(min_length=1)

    @field_validator("repository", "branch", "architecture", "bootstrap_prompt")
    @classmethod
    def _normalize_non_empty(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    @field_validator("agent_models")
    @classmethod
    def _validate_agent_models(cls, value: dict[str, str]) -> dict[str, str]:
        normalized: dict[str, str] = {}
        for role, model in value.items():
            role_name = role.strip()
            model_name = model.strip()
            if not role_name or not model_name:
                raise ValueError("agent_models must contain non-empty role and model names")
            normalized[role_name] = model_name
        if not normalized:
            raise ValueError("agent_models cannot be empty")
        return normalized


class RunOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    identity: RunIdentity
    status: RunStatus
    stop_reason: StopReason
    diff: str = ""
    tests: TestResults | None = None
    logs: list[str] = Field(default_factory=list)
    errors: list[RunError] = Field(default_factory=list)
    final_message: str | None = None


def load_container_instantiation_from_env(
    env: Mapping[str, str] | None = None,
) -> ContainerInstantiation:
    source_env = os_environ if env is None else env
    raw_agent_models = source_env.get("RUN_AGENT_MODELS", "")
    try:
        parsed_agent_models = json.loads(raw_agent_models)
    except json.JSONDecodeError as exc:
        raise ValueError("RUN_AGENT_MODELS must be valid JSON") from exc
    if not isinstance(parsed_agent_models, dict):
        raise ValueError("RUN_AGENT_MODELS must be a JSON object")

    normalized_agent_models: dict[str, str] = {}
    for role, model in parsed_agent_models.items():
        if not isinstance(role, str) or not isinstance(model, str):
            raise ValueError("RUN_AGENT_MODELS values must map string roles to string model names")
        normalized_agent_models[role] = model

    return ContainerInstantiation(
        repository=source_env.get("RUN_REPOSITORY", ""),
        branch=source_env.get("RUN_BRANCH", ""),
        architecture=source_env.get("RUN_ARCHITECTURE", ""),
        agent_models=normalized_agent_models,
        bootstrap_prompt=source_env.get("RUN_BOOTSTRAP_PROMPT", ""),
    )


def new_run_id(now: datetime | None = None) -> str:
    reference = now if now is not None else datetime.now(UTC)
    return f"run-{reference.strftime('%Y%m%dT%H%M%SZ')}-{uuid4().hex[:10]}"


def build_iteration_id(run_id: str, iteration: int) -> str:
    return f"{run_id}-it{iteration:02d}"


def compute_run_fingerprint(run_input: RunInput, agent_config: dict[str, Any]) -> str:
    payload = {
        "prompt": run_input.prompt,
        "metadata": run_input.metadata,
        "target_repo": run_input.target_repo,
        "test_command": run_input.test_command,
        "agent_config": agent_config,
    }
    normalized = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return sha256(normalized.encode("utf-8")).hexdigest()[:16]


def build_run_identity(
    *,
    run_input: RunInput,
    agent_config: dict[str, Any],
    iteration: int,
    run_id: str | None = None,
) -> RunIdentity:
    resolved_run_id = run_id if run_id is not None else new_run_id()
    return RunIdentity(
        run_id=resolved_run_id,
        run_fingerprint=compute_run_fingerprint(run_input, agent_config),
        iteration=iteration,
        iteration_id=build_iteration_id(resolved_run_id, iteration),
    )
