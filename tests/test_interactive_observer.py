from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from llm_autofix_agents.observability.interactive import MarkdownLiveObserver
from llm_autofix_agents.observability.models import (
    AgentExecutionRecord,
    IterationRecord,
    RunDescriptor,
    RunFinishedRecord,
    ToolCallRecord,
)


class InteractiveObserverTests(unittest.TestCase):
    def test_markdown_live_observer_writes_events(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            live_path = Path(tmp_dir) / "results" / "run-1" / "live.md"
            observer = MarkdownLiveObserver(live_path)

            observer.on_run_started(
                run=RunDescriptor(
                    run_id="run-1",
                    architecture="mono_agent",
                    target_repo=".",
                    target_branch="main",
                    run_fingerprint="0123456789abcdef",
                ),
                started_at="2026-01-01T00:00:00+00:00",
            )
            observer.on_iteration_started(
                record=IterationRecord(
                    run_id="run-1",
                    iteration_id="run-1-it01",
                    iteration_index=1,
                    started_at="2026-01-01T00:00:01+00:00",
                    finished_at=None,
                    duration_seconds=None,
                    status="started",
                    stop_reason=None,
                )
            )
            observer.on_tool_call(
                record=ToolCallRecord(
                    tool_call_id="run-1-it01-agent01-tool001",
                    run_id="run-1",
                    iteration_id="run-1-it01",
                    agent_execution_id="run-1-it01-agent01",
                    seq=1,
                    tool_name="read_file",
                    status="success",
                    success=True,
                )
            )
            observer.on_agent_execution_finished(
                record=AgentExecutionRecord(
                    agent_execution_id="run-1-it01-agent01",
                    run_id="run-1",
                    iteration_id="run-1-it01",
                    run_agent_id="run-1-agent",
                    execution_index=1,
                    started_at="2026-01-01T00:00:02+00:00",
                    finished_at="2026-01-01T00:00:03+00:00",
                    duration_seconds=1.0,
                    status="done",
                    reasoning_summary="done",
                    confidence=0.8,
                    notes=None,
                )
            )
            observer.on_run_finished(
                run_finished=RunFinishedRecord(
                    run_id="run-1",
                    finished_at="2026-01-01T00:00:04+00:00",
                    final_status="success",
                    stop_reason="completed",
                    duration_seconds=4.0,
                    total_iterations=1,
                    total_input_tokens=5,
                    total_output_tokens=5,
                    total_tokens=10,
                    files_changed_count=1,
                    resolved=True,
                )
            )

            content = live_path.read_text(encoding="utf-8")
            self.assertIn("# Run run-1", content)
            self.assertIn("## Iteration 1", content)
            self.assertIn("tool 001: read_file -> success", content)
            self.assertIn("## Run finished", content)


if __name__ == "__main__":
    unittest.main()
