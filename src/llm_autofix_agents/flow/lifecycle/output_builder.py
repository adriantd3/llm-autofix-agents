from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.contracts import ErrorCategory, RunError, RunIdentity, RunOutput, RunStatus, StopReason
from llm_autofix_agents.flow.policies.validation import IterationValidationResult
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState


@dataclass(frozen=True)
class RunOutputBuilder:
    """Builds public RunOutput objects and maps domain failures to RunError."""

    def build(
        self,
        *,
        identity: RunIdentity,
        status: RunStatus,
        stop_reason: StopReason,
        state: RunState,
        cfg: RunConfig,
        errors: list[RunError] | None = None,
    ) -> RunOutput:
        return RunOutput(
            identity=identity,
            status=status,
            stop_reason=stop_reason,
            diff=state.latest_diff,
            logs=list(state.accumulated_logs),
            tests=state.latest_tests,
            errors=errors or [],
            artifacts=dict(state.latest_artifacts),
            final_message=state.final_message,
        )

    def validation_failure(
        self,
        *,
        identity: RunIdentity,
        validation: IterationValidationResult,
        state: RunState,
        cfg: RunConfig,
    ) -> RunOutput:
        return self.build(
            identity=identity,
            status=RunStatus.FAILED,
            stop_reason=StopReason.VALIDATION_FAILURE,
            state=state,
            cfg=cfg,
            errors=validation.to_errors(),
        )

    def branch_cleanup_failed(
        self,
        *,
        identity: RunIdentity,
        state: RunState,
        cfg: RunConfig,
        cleanup_error: str,
    ) -> RunOutput:
        return self.build(
            identity=identity,
            status=RunStatus.FAILED,
            stop_reason=StopReason.INFRA_FAILURE,
            state=state,
            cfg=cfg,
            errors=[
                RunError(
                    category=ErrorCategory.INFRA,
                    message="Branch cleanup failed",
                    retryable=False,
                    details={"branch_cleanup_error": cleanup_error},
                )
            ],
        )

    def model_failure(
        self,
        *,
        identity: RunIdentity,
        state: RunState,
        cfg: RunConfig,
        message: str,
        category: ErrorCategory = ErrorCategory.MODEL,
    ) -> RunOutput:
        return self.build(
            identity=identity,
            status=RunStatus.FAILED,
            stop_reason=StopReason.INFRA_FAILURE,
            state=state,
            cfg=cfg,
            errors=[RunError(category=category, message=message, retryable=False)],
        )
