from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from llm_autofix_agents.observability.models import (
    AgentDescriptor,
    AgentExecutionRecord,
    IterationRecord,
    ModelConfigDescriptor,
    RunDescriptor,
    RunFinishedRecord,
    ToolCallRecord,
)
from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore


class ObservabilityTests(unittest.TestCase):
    def test_sqlite_store_persists_minimal_run_graph(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "observability.db"
            store = SQLiteObservabilityStore(db_path=db_path)
            store.initialize()

            architecture_id = store.upsert_architecture("mono_agent")
            self.assertTrue(architecture_id)

            model_config_id = store.upsert_model_config(
                ModelConfigDescriptor(
                    provider="ollama",
                    model="llama3.1:8b",
                    max_turns=3,
                    base_url="http://localhost:11500/v1",
                    tracing_disabled=True,
                )
            )
            self.assertTrue(model_config_id)

            run_id = "run-obs-1"
            store.insert_run_started(
                descriptor=RunDescriptor(
                    run_id=run_id,
                    architecture="mono_agent",
                    target_repo=".",
                    target_branch="main",
                    run_fingerprint="0123456789abcdef",
                ),
                architecture_id=architecture_id,
                started_at="2026-01-01T00:00:00+00:00",
            )

            run_agent_id = store.upsert_run_agent(
                run_id=run_id,
                descriptor=AgentDescriptor(
                    agent_name="baseline",
                    agent_role="fixer",
                    model_config=ModelConfigDescriptor(
                        provider="ollama",
                        model="llama3.1:8b",
                        max_turns=3,
                        base_url="http://localhost:11500/v1",
                        tracing_disabled=True,
                    ),
                    tool_profile="full",
                    agent_order=1,
                ),
                model_config_id=model_config_id,
                instructions_hash="abcdef0123456789",
            )
            self.assertTrue(run_agent_id)

            iteration_id = f"{run_id}-it01"
            store.insert_iteration(
                IterationRecord(
                    run_id=run_id,
                    iteration_id=iteration_id,
                    iteration_index=1,
                    started_at="2026-01-01T00:00:01+00:00",
                    finished_at="2026-01-01T00:00:10+00:00",
                    duration_seconds=9.0,
                    status="done",
                    stop_reason="completed",
                    input_tokens=10,
                    output_tokens=8,
                    total_tokens=18,
                    tool_calls_count=1,
                    changed_files_count=1,
                    repo_changed=True,
                    test_exit_code=0,
                    test_timed_out=False,
                    test_signature="sig-ok",
                )
            )

            agent_execution_id = f"{run_id}-it01-agent01"
            store.insert_agent_execution(
                AgentExecutionRecord(
                    agent_execution_id=agent_execution_id,
                    run_id=run_id,
                    iteration_id=iteration_id,
                    run_agent_id=run_agent_id,
                    execution_index=1,
                    started_at="2026-01-01T00:00:02+00:00",
                    finished_at="2026-01-01T00:00:09+00:00",
                    duration_seconds=7.0,
                    status="done",
                    reasoning_summary="fix candidate",
                    confidence=0.8,
                    notes=None,
                    input_tokens=10,
                    output_tokens=8,
                    total_tokens=18,
                    tool_calls_count=1,
                )
            )

            store.insert_tool_call(
                ToolCallRecord(
                    tool_call_id=f"{agent_execution_id}-tool001",
                    run_id=run_id,
                    iteration_id=iteration_id,
                    agent_execution_id=agent_execution_id,
                    seq=1,
                    tool_name="read_file",
                    status="success",
                    success=True,
                )
            )

            store.update_run_finished(
                RunFinishedRecord(
                    run_id=run_id,
                    finished_at="2026-01-01T00:00:11+00:00",
                    final_status="success",
                    stop_reason="completed",
                    duration_seconds=11.0,
                    total_iterations=1,
                    total_input_tokens=10,
                    total_output_tokens=8,
                    total_tokens=18,
                    files_changed_count=1,
                    resolved=True,
                    live_log_path="results/run-obs-1/live.md",
                    summary_path="results/run-obs-1/summary.json",
                    diff_path="results/run-obs-1/it01/patch.diff",
                )
            )

            with sqlite3.connect(db_path) as conn:
                run_count = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
                iteration_count = conn.execute("SELECT COUNT(*) FROM iterations").fetchone()[0]
                execution_count = conn.execute("SELECT COUNT(*) FROM agent_executions").fetchone()[0]
                tool_count = conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]

            self.assertEqual(run_count, 1)
            self.assertEqual(iteration_count, 1)
            self.assertEqual(execution_count, 1)
            self.assertEqual(tool_count, 1)


if __name__ == "__main__":
    unittest.main()
