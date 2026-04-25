from __future__ import annotations

from dataclasses import dataclass

from llm_autofix_agents.flow.models import TestExecution
from llm_autofix_agents.flow.runtime.context import RunConfig
from llm_autofix_agents.llm.provider import AgentFixIterationRecord
from llm_autofix_agents.observability import (
    FileChangeRecord,
    IterationRecord,
    RunObserver,
    TestExecutionRecord,
    make_file_change_id,
    make_test_execution_id,
)


@dataclass(frozen=True)
class IterationEvents:
    """Emits iteration-local observability events."""

    def started(self, *, cfg: RunConfig, iteration_id: str, iteration_index: int) -> None:
        cfg.observer.on_iteration_started(
            record=IterationRecord.started(
                run_id=cfg.run_id,
                iteration_id=iteration_id,
                iteration_index=iteration_index,
            )
        )

    def finished(
        self,
        *,
        cfg: RunConfig,
        iteration_id: str,
        iteration_index: int,
        started_at: str,
        proposal: AgentFixIterationRecord,
        duration_seconds: float,
        tool_calls_count: int,
        changed_files_count: int,
        repo_changed: bool,
        test_execution: TestExecution,
    ) -> None:
        cfg.observer.on_iteration_finished(
            record=IterationRecord.finished(
                run_id=cfg.run_id,
                iteration_id=iteration_id,
                iteration_index=iteration_index,
                started_at=started_at,
                status=proposal.status,
                duration_seconds=duration_seconds,
                input_tokens=proposal.input_tokens,
                output_tokens=proposal.output_tokens,
                total_tokens=proposal.total_tokens,
                tool_calls_count=tool_calls_count,
                changed_files_count=changed_files_count,
                repo_changed=repo_changed,
                test_exit_code=test_execution.exit_code,
                test_timed_out=test_execution.timed_out,
                test_signature=test_execution.signature,
            )
        )

    def test_execution(
        self,
        *,
        observer: RunObserver,
        run_id: str,
        phase: str,
        test_execution: TestExecution,
        command: str | None,
        iteration: int,
        iteration_id: str | None = None,
        agent_execution_id: str | None = None,
    ) -> None:
        observer.on_test_execution(
            record=TestExecutionRecord.create(
                test_execution_id=make_test_execution_id(run_id, iteration),
                run_id=run_id,
                phase=phase,
                command=command,
                exit_code=test_execution.exit_code,
                timed_out=test_execution.timed_out,
                signature=test_execution.signature,
                iteration_id=iteration_id,
                agent_execution_id=agent_execution_id,
            )
        )

    def file_changes(
        self,
        *,
        cfg: RunConfig,
        iteration: int,
        iteration_id: str,
        agent_execution_id: str,
        changed_files: list[str],
    ) -> None:
        for index, path in enumerate(changed_files, start=1):
            cfg.observer.on_file_change(
                record=FileChangeRecord.create(
                    file_change_id=make_file_change_id(cfg.run_id, iteration, index),
                    run_id=cfg.run_id,
                    path=path,
                    change_type="modified",
                    detected_by="snapshot_diff",
                    iteration_id=iteration_id,
                    agent_execution_id=agent_execution_id,
                )
            )
