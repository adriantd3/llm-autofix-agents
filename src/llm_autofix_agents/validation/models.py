from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field


class ValidatorOutput(BaseModel):
    """Structured verdict produced by the LLM validator."""

    verdict: Literal["CORRECT", "PLAUSIBLE", "OVERFITTING", "FAIL"]
    confidence: float = Field(ge=0.0, le=1.0)
    test_passed: bool
    patch_semantically_matches: bool | None = None
    justification: str = Field(min_length=1)


@dataclass(frozen=True)
class RunValidationInput:
    """All context required to validate a single run."""

    run_id: str
    problem_id: str
    benchmark_name: str
    dataset_type: str  # "quixbugs" | "bugsinpy"
    test_exit_code: int | None
    generated_patch: str | None
    canonical_patch: str | None
    test_output: str | None
