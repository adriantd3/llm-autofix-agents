from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path

from llm_autofix_agents.contracts import RunOutput, RunStatus
from llm_autofix_agents.flow.runtime.context import RunConfig, RunState
from llm_autofix_agents.observability import write_summary

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class FinalizedRunPaths:
    summary_path: Path
    live_log_path: str | None
    observability_db_path: str


@dataclass(frozen=True)
class RunFinalizer:
    """Owns final summary, final observability event, and final output enrichment."""

    def finalize(self, *, output: RunOutput, state: RunState, cfg: RunConfig) -> RunOutput:
        duration_seconds = self._duration_seconds(state)
        paths = self._paths(cfg)

        self._write_summary(output=output, state=state, cfg=cfg, paths=paths, duration_seconds=duration_seconds)
        self._emit_run_finished(output=output, state=state, cfg=cfg, paths=paths, duration_seconds=duration_seconds)
        self._attach_observability_artifacts(output=output, cfg=cfg, paths=paths)
        self._append_observability_logs(output=output, state=state, cfg=cfg, duration_seconds=duration_seconds)

        logger.info("completed run_id=%s status=%s", cfg.run_id, output.status.value)
        return output

    def _duration_seconds(self, state: RunState) -> float:
        return max(0.0, time.perf_counter() - state.run_started_monotonic)

    def _paths(self, cfg: RunConfig) -> FinalizedRunPaths:
        obs = cfg.observability
        summary_path = cfg.results_dir / "summary.json"
        return FinalizedRunPaths(
            summary_path=summary_path,
            live_log_path=obs.live_log_display_path(repo_root=cfg.repo_root),
            observability_db_path=obs.db_display_path(repo_root=cfg.repo_root),
        )

    def _write_summary(
        self,
        *,
        output: RunOutput,
        state: RunState,
        cfg: RunConfig,
        paths: FinalizedRunPaths,
        duration_seconds: float,
    ) -> None:
        write_summary(
            summary_path=paths.summary_path,
            run_id=cfg.run_id,
            status=output.status.value,
            stop_reason=output.stop_reason.value,
            duration_seconds=duration_seconds,
            iterations=output.identity.iteration,
            input_tokens=state.total_input_tokens,
            output_tokens=state.total_output_tokens,
            total_tokens=state.total_tokens,
            changed_files_count=state.max_changed_files_count,
            observability_db=paths.observability_db_path,
            live_log=paths.live_log_path,
        )

    def _emit_run_finished(
        self,
        *,
        output: RunOutput,
        state: RunState,
        cfg: RunConfig,
        paths: FinalizedRunPaths,
        duration_seconds: float,
    ) -> None:
        cfg.observability.telemetry.finish_run(
            final_status=output.status.value,
            stop_reason=output.stop_reason.value,
            duration_seconds=duration_seconds,
            total_iterations=output.identity.iteration,
            total_input_tokens=state.total_input_tokens,
            total_output_tokens=state.total_output_tokens,
            total_tokens=state.total_tokens,
            files_changed_count=state.max_changed_files_count,
            resolved=output.status == RunStatus.SUCCESS,
            live_log_path=paths.live_log_path,
            summary_path=_display_path(paths.summary_path, cfg.repo_root),
        )

    def _attach_observability_artifacts(
        self,
        *,
        output: RunOutput,
        cfg: RunConfig,
        paths: FinalizedRunPaths,
    ) -> None:
        output.artifacts = {
            **output.artifacts,
            "observability": {
                "backend": "sqlite" if cfg.observability.sqlite_store else "disabled",
                "db_path": paths.observability_db_path,
            },
        }

    def _append_observability_logs(
        self,
        *,
        output: RunOutput,
        state: RunState,
        cfg: RunConfig,
        duration_seconds: float,
    ) -> None:
        output.logs.extend(
            [
                "stage=observability",
                f"observability_backend={'sqlite' if cfg.observability.sqlite_store else 'disabled'}",
                f"observability_duration_seconds={duration_seconds:.3f}",
                f"observability_total_tokens={state.total_tokens}",
            ]
        )


def _display_path(path: Path, repo_root: Path) -> str:
    try:
        return path.relative_to(repo_root).as_posix()
    except ValueError:
        return path.as_posix()

