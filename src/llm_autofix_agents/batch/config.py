from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

from llm_autofix_agents.contracts import RunArchitecture


class BugEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    program: str | None = None
    test: str | None = None
    test_command: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id")
    @classmethod
    def _strip_whitespace(cls, value: str) -> str:
        return value.strip()

    @field_validator("program", "test")
    @classmethod
    def _strip_optional_whitespace(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class RepositoryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    branch: str | None = None

    @field_validator("url")
    @classmethod
    def _strip_url(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("url cannot be empty")
        return normalized

    @field_validator("branch")
    @classmethod
    def _strip_branch(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TestConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    command_template: str = Field(min_length=1)

    @field_validator("command_template")
    @classmethod
    def _strip_template(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("command_template cannot be empty")
        return normalized


class DatasetConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1)
    name: str = Field(min_length=1)
    language: str = Field(min_length=1)
    repository: RepositoryConfig | None = None
    test: TestConfig | None = None
    tooling: dict[str, Any] = Field(default_factory=dict)
    bugs: list[BugEntry] = Field(min_length=1)

    @field_validator("name", "language", "type")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("value cannot be empty")
        return normalized

    def resolve_test_command(self, bug: BugEntry) -> str:
        if bug.test_command is not None:
            return bug.test_command
        if self.test is not None:
            return self.test.command_template.format(
                bug_id=bug.id,
                program=bug.program or "",
                test=bug.test or "",
                **bug.metadata,
            )
        tooling_test = self.tooling.get("test_command")
        if tooling_test is not None:
            return str(tooling_test)
        raise ValueError(f"No test_command for bug '{bug.id}' and no dataset-level test config")


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str = "ollama"
    model: str = Field(min_length=1)
    max_turns: int = 20
    agent_models: dict[str, str] | None = None

    @field_validator("model", "provider")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return value.strip()

    def resolve_agent_models(self, architecture: RunArchitecture) -> dict[str, str]:
        if self.agent_models is not None:
            return self.agent_models
        if architecture == RunArchitecture.MONO_AGENT:
            return {"main": self.model}
        if architecture == RunArchitecture.MULTI_AGENT_ORCHESTRATOR:
            return {
                "manager": self.model,
                "localizer": self.model,
                "patcher": self.model,
                "validator": self.model,
            }
        if architecture == RunArchitecture.PLANNER_EXECUTOR:
            return {
                "planner": self.model,
                "executor": self.model,
            }
        return {
            "triage": self.model,
            "localizer": self.model,
            "validator": self.model,
            "patcher": self.model,
        }


class GlobalSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    architecture: RunArchitecture
    llm: LLMSettings
    max_iterations: int = 6
    timeout_seconds: int = 300
    iteration_timeout_seconds: int | None = None
    prompt_template: str | None = None
    capture_errors: bool = True
    cleanup_workspaces: bool = False

    @field_validator("prompt_template")
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class BatchConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    name: str = Field(min_length=1)
    description: str | None = None
    dataset: str = Field(min_length=1)
    global_settings: GlobalSettings = Field(alias="global")
    bugs: list[str] = Field(min_length=1)

    @field_validator("name", "dataset")
    @classmethod
    def _strip_required_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("bugs")
    @classmethod
    def _validate_bugs(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("bugs list cannot be empty")
        has_all = "all" in value
        if has_all and len(value) > 1:
            raise ValueError("When 'all' is specified, no other bug IDs should be listed")
        return value


def load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a YAML mapping in {path}, got {type(data).__name__}")
    return data


def load_dataset_config(path: Path) -> DatasetConfig:
    data = load_yaml(path)
    return DatasetConfig(**data)


def load_batch_config(path: Path) -> tuple[BatchConfig, Path]:
    data = load_yaml(path)
    config = BatchConfig(**data)
    dataset_path = (path.parent / config.dataset).resolve()
    return config, dataset_path


def expand_bugs(batch_config: BatchConfig, dataset_config: DatasetConfig) -> list[BugEntry]:
    if "all" in batch_config.bugs:
        return list(dataset_config.bugs)
    bug_map = {bug.id: bug for bug in dataset_config.bugs}
    resolved: list[BugEntry] = []
    for bug_id in batch_config.bugs:
        if bug_id not in bug_map:
            raise ValueError(f"Bug '{bug_id}' not found in dataset '{dataset_config.name}'")
        resolved.append(bug_map[bug_id])
    return resolved
