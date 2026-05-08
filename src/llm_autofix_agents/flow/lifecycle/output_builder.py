from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.contracts import ErrorCategory, RunError, RunIdentity, RunOutput, RunStatus, StopReason
from llm_autofix_agents.flow.policies.validation import IterationValidationResult
from llm_autofix_agents.flow.runtime.context import RunState


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
        errors: list[RunError] | None = None,
    ) -> RunOutput:
        artifacts = dict(state.latest_artifacts)
        if errors:
            artifacts["errors"] = [e.model_dump() for e in errors]
        return RunOutput(
            identity=identity,
            status=status,
            stop_reason=stop_reason,
            logs=list(state.accumulated_logs),
            artifacts=artifacts,
        )

    def validation_failure(
        self,
        *,
        identity: RunIdentity,
        validation: IterationValidationResult,
        state: RunState,
    ) -> RunOutput:
        return self.build(
            identity=identity,
            status=RunStatus.FAILED,
            stop_reason=StopReason.VALIDATION_FAILURE,
            state=state,
            errors=validation.to_errors(),
        )

    def branch_cleanup_failed(
        self,
        *,
        identity: RunIdentity,
        state: RunState,
        cleanup_error: str,
    ) -> RunOutput:
        return self.build(
            identity=identity,
            status=RunStatus.FAILED,
            stop_reason=StopReason.INFRA_FAILURE,
            state=state,
            errors=[
                RunError(
                    category=ErrorCategory.INFRA,
                    message="Branch cleanup failed",
                    retryable=False,
                    details={"branch_cleanup_error": cleanup_error},
                )
            ],
        )

    def exception_failure(
        self,
        *,
        identity: RunIdentity,
        state: RunState,
        message: str,
        category: ErrorCategory = ErrorCategory.MODEL,
    ) -> RunOutput:
        return self.build(
            identity=identity,
            status=RunStatus.FAILED,
            stop_reason=_stop_reason_for_category(category),
            state=state,
            errors=[RunError(category=category, message=message, retryable=False)],
        )


def _stop_reason_for_category(category: ErrorCategory) -> StopReason:
    if category == ErrorCategory.VALIDATION:
        return StopReason.VALIDATION_FAILURE
    if category in {ErrorCategory.MODEL, ErrorCategory.TOOL}:
        return StopReason.TOOL_FAILURE
    return StopReason.INFRA_FAILURE

