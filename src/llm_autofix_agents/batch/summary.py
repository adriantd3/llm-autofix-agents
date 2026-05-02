from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field


class BugRunResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    bug_id: str = Field(min_length=1)
    status: str = Field(min_length=1)
    run_id: str | None = None
    duration_seconds: float = 0.0
    iterations: int | None = None
    exit_code: int | None = None
    error_message: str | None = None


class BatchSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    batch_name: str = Field(min_length=1)
    config_path: str = Field(min_length=1)
    dataset_name: str = Field(min_length=1)
    architecture: str = Field(min_length=1)
    model: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    started_at: datetime
    completed_at: datetime
    total_bugs: int = Field(ge=0)
    successful: int = Field(ge=0)
    failed: int = Field(ge=0)
    timed_out: int = Field(ge=0)
    infra_failures: int = Field(ge=0)
    results: list[BugRunResult] = Field(default_factory=list)


def new_batch_id(name: str, now: datetime | None = None) -> str:
    reference = now if now is not None else datetime.now(UTC)
    ts = reference.strftime("%Y%m%dT%H%M%SZ")
    return f"batch-{name}-{ts}"
