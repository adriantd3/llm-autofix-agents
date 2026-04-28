from __future__ import annotations

from llm_autofix_agents.contracts import ErrorCategory


class FlowError(RuntimeError):
    """Base flow-level exception for failure classification."""


class WorkspaceError(FlowError):
    pass


class ValidationError(FlowError):
    pass


class ProviderExecutionError(FlowError):
    pass


class ObservabilityError(FlowError):
    pass


def error_category_from_exception(exc: Exception) -> ErrorCategory:
    try:
        from llm_autofix_agents.llm.provider import ProviderCallError
    except Exception:  # pragma: no cover - defensive import guard
        ProviderCallError = None  # type: ignore[assignment]

    if ProviderCallError is not None and isinstance(exc, ProviderCallError):
        return ErrorCategory.MODEL
    if isinstance(exc, ProviderExecutionError):
        return ErrorCategory.MODEL
    if isinstance(exc, ValidationError):
        return ErrorCategory.VALIDATION
    if isinstance(exc, (WorkspaceError, ObservabilityError)):
        return ErrorCategory.INFRA
    return ErrorCategory.UNKNOWN
