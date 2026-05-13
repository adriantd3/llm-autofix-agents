from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class ProviderCallEvent:
    event_type: Literal[
        "retryable_failure",
        "retry_scheduled",
        "retry_succeeded",
        "retries_exhausted",
        "non_retryable_failure",
    ]
    agent_execution_id: str | None
    attempt: int
    total_attempts: int
    status_code: int | None = None
    error_type: str | None = None
    error_message_short: str | None = None
    tool_calls_count: int | None = None
    retry_delay_seconds: float | None = None
    rerun_full_runner: bool = True


ProviderCallEventCallback = Callable[[ProviderCallEvent], None]


@dataclass(frozen=True)
class ProviderRetryEventEmitter:
    callback: ProviderCallEventCallback | None
    agent_execution_id: str | None
    total_attempts: int
    tool_calls_count_getter: Callable[[], int | None]

    def retry_succeeded(self, *, attempt: int) -> None:
        self._emit(
            ProviderCallEvent(
                event_type="retry_succeeded",
                agent_execution_id=self.agent_execution_id,
                attempt=attempt,
                total_attempts=self.total_attempts,
                tool_calls_count=self.tool_calls_count_getter(),
            )
        )

    def non_retryable_failure(self, *, attempt: int, status_code: int | None, error: Exception) -> None:
        self._emit(
            ProviderCallEvent(
                event_type="non_retryable_failure",
                agent_execution_id=self.agent_execution_id,
                attempt=attempt,
                total_attempts=self.total_attempts,
                status_code=status_code,
                error_type=error.__class__.__name__,
                error_message_short=_short_error_message(error),
                tool_calls_count=self.tool_calls_count_getter(),
            )
        )

    def retries_exhausted(self, *, attempt: int, status_code: int | None, error: Exception) -> None:
        self._emit(
            ProviderCallEvent(
                event_type="retries_exhausted",
                agent_execution_id=self.agent_execution_id,
                attempt=attempt,
                total_attempts=self.total_attempts,
                status_code=status_code,
                error_type=error.__class__.__name__,
                error_message_short=_short_error_message(error),
                tool_calls_count=self.tool_calls_count_getter(),
            )
        )

    def retryable_failure(self, *, attempt: int, status_code: int | None, error: Exception) -> None:
        self._emit(
            ProviderCallEvent(
                event_type="retryable_failure",
                agent_execution_id=self.agent_execution_id,
                attempt=attempt,
                total_attempts=self.total_attempts,
                status_code=status_code,
                error_type=error.__class__.__name__,
                error_message_short=_short_error_message(error),
                tool_calls_count=self.tool_calls_count_getter(),
            )
        )

    def retry_scheduled(
        self,
        *,
        attempt: int,
        status_code: int | None,
        error: Exception,
        retry_delay_seconds: float,
        rerun_full_runner: bool = True,
    ) -> None:
        self._emit(
            ProviderCallEvent(
                event_type="retry_scheduled",
                agent_execution_id=self.agent_execution_id,
                attempt=attempt,
                total_attempts=self.total_attempts,
                status_code=status_code,
                error_type=error.__class__.__name__,
                error_message_short=_short_error_message(error),
                tool_calls_count=self.tool_calls_count_getter(),
                retry_delay_seconds=retry_delay_seconds,
                rerun_full_runner=rerun_full_runner,
            )
        )

    def _emit(self, event: ProviderCallEvent) -> None:
        if self.callback is None:
            return
        self.callback(event)


def _short_error_message(error: Exception) -> str:
    return str(error).strip()[:500] or error.__class__.__name__
