from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from llm_autofix_agents.observability import APRRunHooks, RunObserver
from llm_autofix_agents.observability.models import (
    AgentDescriptor,
    AgentExecutionRecord,
    FileChangeRecord,
    IterationRecord,
    ModelConfigDescriptor,
    RunDescriptor,
    RunFinishedRecord,
    TestExecutionRecord,
    make_file_change_id,
    make_test_execution_id,
    utc_now_iso,
)


@dataclass(frozen=True)
class RunTelemetry:
    """High-level semantic telemetry API for APR run lifecycle."""

    observer: RunObserver
    run_id: str

    def start_run(
        self,
        *,
        architecture: str,
        target_repo: str | None,
        target_branch: str | None,
        run_fingerprint: str,
        prompt: str,
        benchmark_name: str | None,
        problem_id: str | None,
    ) -> None:
        self.observer.on_run_started(
            run=RunDescriptor(
                run_id=self.run_id,
                architecture=architecture,
                target_repo=target_repo,
                target_branch=target_branch,
                run_fingerprint=run_fingerprint,
                prompt_hash=sha256(prompt.encode("utf-8")).hexdigest()[:16],
                benchmark_name=benchmark_name,
                problem_id=problem_id,
            ),
            started_at=utc_now_iso(),
        )

    def register_agent(
        self,
        *,
        agent_name: str,
        agent_role: str,
        provider: str,
        model: str,
        max_turns: int,
        tool_profile: str,
        instructions: str,
        base_url: str | None,
        tracing_disabled: bool,
        agent_order: int = 1,
    ) -> str:
        run_agent_id = self.observer.on_run_agent_registered(
            run_id=self.run_id,
            agent=AgentDescriptor(
                agent_name=agent_name,
                agent_role=agent_role,
                model_config=ModelConfigDescriptor(
                    provider=provider,
                    model=model,
                    max_turns=max_turns,
                    base_url=base_url,
                    tracing_disabled=tracing_disabled,
                ),
                tool_profile=tool_profile,
                agent_order=agent_order,
            ),
            instructions_hash=sha256(instructions.encode("utf-8")).hexdigest()[:16],
        )
        return run_agent_id or f"{self.run_id}-agent-{agent_name}"

    def start_iteration(self, *, iteration_id: str, iteration_index: int) -> IterationTelemetry:
        self.observer.on_iteration_started(
            record=IterationRecord.started(
                run_id=self.run_id,
                iteration_id=iteration_id,
                iteration_index=iteration_index,
            )
        )
        return IterationTelemetry(
            observer=self.observer,
            run_id=self.run_id,
            iteration_id=iteration_id,
            iteration_index=iteration_index,
        )

    def finish_run(
        self,
        *,
        final_status: str,
        stop_reason: str,
        duration_seconds: float,
        total_iterations: int,
        total_input_tokens: int,
        total_output_tokens: int,
        total_tokens: int,
        files_changed_count: int,
        resolved: bool,
        live_log_path: str | None,
        summary_path: str | None,
    ) -> None:
        self.observer.on_run_finished(
            run_finished=RunFinishedRecord(
                run_id=self.run_id,
                finished_at=utc_now_iso(),
                final_status=final_status,
                stop_reason=stop_reason,
                duration_seconds=duration_seconds,
                total_iterations=total_iterations,
                total_input_tokens=total_input_tokens,
                total_output_tokens=total_output_tokens,
                total_tokens=total_tokens,
                files_changed_count=files_changed_count,
                resolved=resolved,
                live_log_path=live_log_path,
                summary_path=summary_path,
            )
        )

    def record_test_execution(
        self,
        *,
        phase: str,
        command: str | None,
        exit_code: int,
        timed_out: bool,
        signature: str,
        iteration: int,
        agent_execution_id: str | None = None,
    ) -> None:
        """Record a test execution (e.g., baseline) at the run level."""
        self.observer.on_test_execution(
            record=TestExecutionRecord.create(
                test_execution_id=make_test_execution_id(self.run_id, iteration),
                run_id=self.run_id,
                phase=phase,
                command=command,
                exit_code=exit_code,
                timed_out=timed_out,
                signature=signature,
                iteration_id=None,
                agent_execution_id=agent_execution_id,
            )
        )


@dataclass(frozen=True)
class IterationTelemetry:
    """Contextual telemetry for one iteration."""

    observer: RunObserver
    run_id: str
    iteration_id: str
    iteration_index: int

    def start_agent_execution(
        self,
        *,
        run_agent_id: str,
        execution_index: int,
    ) -> AgentExecutionTelemetry:
        agent_execution_id = f"{self.run_id}-it{self.iteration_index:02d}-agent{execution_index:02d}"
        started_at = utc_now_iso()
        self.observer.on_agent_execution_started(
            record=AgentExecutionRecord.started(
                agent_execution_id=agent_execution_id,
                run_id=self.run_id,
                iteration_id=self.iteration_id,
                run_agent_id=run_agent_id,
                execution_index=execution_index,
            )
        )
        return AgentExecutionTelemetry(
            observer=self.observer,
            run_id=self.run_id,
            iteration_id=self.iteration_id,
            iteration_index=self.iteration_index,
            run_agent_id=run_agent_id,
            agent_execution_id=agent_execution_id,
            execution_index=execution_index,
            started_at=started_at,
        )

    def finish_iteration(
        self,
        *,
        started_at: str,
        status: str,
        duration_seconds: float,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        tool_calls_count: int,
        changed_files_count: int,
        repo_changed: bool,
        test_exit_code: int,
        test_timed_out: bool,
        test_signature: str,
    ) -> None:
        self.observer.on_iteration_finished(
            record=IterationRecord.finished(
                run_id=self.run_id,
                iteration_id=self.iteration_id,
                iteration_index=self.iteration_index,
                started_at=started_at,
                status=status,
                duration_seconds=duration_seconds,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                tool_calls_count=tool_calls_count,
                changed_files_count=changed_files_count,
                repo_changed=repo_changed,
                test_exit_code=test_exit_code,
                test_timed_out=test_timed_out,
                test_signature=test_signature,
            )
        )

    def record_test_execution(
        self,
        *,
        phase: str,
        command: str | None,
        exit_code: int,
        timed_out: bool,
        signature: str,
        agent_execution_id: str | None = None,
    ) -> None:
        self.observer.on_test_execution(
            record=TestExecutionRecord.create(
                test_execution_id=make_test_execution_id(self.run_id, self.iteration_index),
                run_id=self.run_id,
                phase=phase,
                command=command,
                exit_code=exit_code,
                timed_out=timed_out,
                signature=signature,
                iteration_id=self.iteration_id,
                agent_execution_id=agent_execution_id,
            )
        )

    def record_file_changes(
        self,
        *,
        agent_execution_id: str,
        modified_files: list[str],
        added_files: list[str],
        deleted_files: list[str],
        untracked_files: list[str],
    ) -> None:
        index = 0
        for path in modified_files:
            index += 1
            self.observer.on_file_change(
                record=FileChangeRecord.create(
                    file_change_id=make_file_change_id(self.run_id, self.iteration_index, index),
                    run_id=self.run_id,
                    path=path,
                    change_type="modified",
                    detected_by="snapshot_diff",
                    iteration_id=self.iteration_id,
                    agent_execution_id=agent_execution_id,
                )
            )
        for path in added_files:
            index += 1
            self.observer.on_file_change(
                record=FileChangeRecord.create(
                    file_change_id=make_file_change_id(self.run_id, self.iteration_index, index),
                    run_id=self.run_id,
                    path=path,
                    change_type="added",
                    detected_by="snapshot_diff",
                    iteration_id=self.iteration_id,
                    agent_execution_id=agent_execution_id,
                )
            )
        for path in deleted_files:
            index += 1
            self.observer.on_file_change(
                record=FileChangeRecord.create(
                    file_change_id=make_file_change_id(self.run_id, self.iteration_index, index),
                    run_id=self.run_id,
                    path=path,
                    change_type="deleted",
                    detected_by="snapshot_diff",
                    iteration_id=self.iteration_id,
                    agent_execution_id=agent_execution_id,
                )
            )
        for path in untracked_files:
            index += 1
            self.observer.on_file_change(
                record=FileChangeRecord.create(
                    file_change_id=make_file_change_id(self.run_id, self.iteration_index, index),
                    run_id=self.run_id,
                    path=path,
                    change_type="untracked",
                    detected_by="snapshot_diff",
                    iteration_id=self.iteration_id,
                    agent_execution_id=agent_execution_id,
                )
            )


@dataclass(frozen=True)
class AgentExecutionTelemetry:
    """Contextual telemetry for one agent execution."""

    observer: RunObserver
    run_id: str
    iteration_id: str
    iteration_index: int
    run_agent_id: str
    agent_execution_id: str
    execution_index: int
    started_at: str

    def create_hooks(self) -> APRRunHooks:
        return APRRunHooks(
            observer=self.observer,
            run_id=self.run_id,
            iteration_id=self.iteration_id,
            agent_execution_id=self.agent_execution_id,
        )

    def finish(
        self,
        *,
        proposal: object,
        tool_calls_count: int,
    ) -> None:
        from llm_autofix_agents.llm.provider import AgentFixIterationRecord

        p = proposal if isinstance(proposal, AgentFixIterationRecord) else None
        self.observer.on_agent_execution_finished(
            record=AgentExecutionRecord.finished(
                agent_execution_id=self.agent_execution_id,
                run_id=self.run_id,
                iteration_id=self.iteration_id,
                run_agent_id=self.run_agent_id,
                execution_index=self.execution_index,
                started_at=self.started_at,
                status=p.status if p else "unknown",
                reasoning_summary=p.reasoning_summary if p else "",
                confidence=p.confidence if p else 0.0,
                notes=p.notes if p else None,
                input_tokens=p.input_tokens if p else 0,
                output_tokens=p.output_tokens if p else 0,
                total_tokens=p.total_tokens if p else 0,
                tool_calls_count=tool_calls_count,
            )
        )
