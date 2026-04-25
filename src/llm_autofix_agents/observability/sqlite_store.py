from __future__ import annotations

import json
import sqlite3
from hashlib import sha256
from pathlib import Path

from llm_autofix_agents.observability.models import (
    AgentDescriptor,
    AgentExecutionRecord,
    FileChangeRecord,
    IterationRecord,
    ModelConfigDescriptor,
    RunDescriptor,
    RunFinishedRecord,
    TestExecutionRecord,
    ToolCallRecord,
)
from llm_autofix_agents.observability.sqlite_schema import SCHEMA_VERSION, schema_init_sql


def stable_id(prefix: str, payload: str) -> str:
    digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"


class SQLiteObservabilityStore:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    @property
    def db_path(self) -> Path:
        return self._db_path

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(schema_init_sql())
            conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")

    def upsert_architecture(self, name: str, description: str | None = None) -> str:
        architecture_id = stable_id("arch", name.strip().lower())
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO architectures (architecture_id, name, description)
                VALUES (?, ?, ?)
                ON CONFLICT(name) DO UPDATE SET description = COALESCE(excluded.description, architectures.description)
                """,
                (architecture_id, name, description),
            )
        return architecture_id

    def upsert_model_config(self, descriptor: ModelConfigDescriptor) -> str:
        extra_json = "{}"
        payload = json.dumps(
            {
                "provider": descriptor.provider,
                "model": descriptor.model,
                "base_url": descriptor.base_url,
                "max_turns": descriptor.max_turns,
                "tracing_disabled": descriptor.tracing_disabled,
                "extra_json": extra_json,
            },
            sort_keys=True,
            ensure_ascii=True,
        )
        model_config_id = stable_id("model", payload)

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO model_configs (
                    model_config_id,
                    provider,
                    model,
                    base_url,
                    max_turns,
                    tracing_disabled,
                    extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(model_config_id) DO UPDATE SET
                    provider = excluded.provider,
                    model = excluded.model,
                    base_url = excluded.base_url,
                    max_turns = excluded.max_turns,
                    tracing_disabled = excluded.tracing_disabled,
                    extra_json = excluded.extra_json
                """,
                (
                    model_config_id,
                    descriptor.provider,
                    descriptor.model,
                    descriptor.base_url,
                    descriptor.max_turns,
                    1 if descriptor.tracing_disabled else 0,
                    extra_json,
                ),
            )
        return model_config_id

    def upsert_run_agent(
        self,
        *,
        run_id: str,
        descriptor: AgentDescriptor,
        model_config_id: str,
        instructions_hash: str | None = None,
    ) -> str:
        payload = f"{run_id}|{descriptor.agent_name}|{descriptor.agent_role}|{descriptor.agent_order}"
        run_agent_id = stable_id("ra", payload)
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO run_agents (
                    run_agent_id,
                    run_id,
                    agent_name,
                    agent_role,
                    agent_order,
                    model_config_id,
                    instructions_hash,
                    tool_profile
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, agent_name) DO UPDATE SET
                    agent_role = excluded.agent_role,
                    agent_order = excluded.agent_order,
                    model_config_id = excluded.model_config_id,
                    instructions_hash = excluded.instructions_hash,
                    tool_profile = excluded.tool_profile
                """,
                (
                    run_agent_id,
                    run_id,
                    descriptor.agent_name,
                    descriptor.agent_role,
                    descriptor.agent_order,
                    model_config_id,
                    instructions_hash,
                    descriptor.tool_profile,
                ),
            )
        return run_agent_id

    def insert_run_started(self, *, descriptor: RunDescriptor, architecture_id: str, started_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO runs (
                    run_id,
                    architecture_id,
                    started_at,
                    target_repo,
                    target_branch,
                    benchmark_name,
                    problem_id,
                    prompt_hash,
                    run_fingerprint
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    descriptor.run_id,
                    architecture_id,
                    started_at,
                    descriptor.target_repo,
                    descriptor.target_branch,
                    descriptor.benchmark_name,
                    descriptor.problem_id,
                    descriptor.prompt_hash,
                    descriptor.run_fingerprint,
                ),
            )

    def update_run_finished(self, record: RunFinishedRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE runs
                SET
                    finished_at = ?,
                    final_status = ?,
                    stop_reason = ?,
                    resolved = ?,
                    duration_seconds = ?,
                    total_iterations = ?,
                    total_input_tokens = ?,
                    total_output_tokens = ?,
                    total_tokens = ?,
                    files_changed_count = ?,
                    live_log_path = ?,
                    summary_path = ?,
                    diff_path = ?
                WHERE run_id = ?
                """,
                (
                    record.finished_at,
                    record.final_status,
                    record.stop_reason,
                    1 if record.resolved else 0,
                    record.duration_seconds,
                    record.total_iterations,
                    record.total_input_tokens,
                    record.total_output_tokens,
                    record.total_tokens,
                    record.files_changed_count,
                    record.live_log_path,
                    record.summary_path,
                    record.diff_path,
                    record.run_id,
                ),
            )

    def insert_iteration(self, record: IterationRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO iterations (
                    iteration_id,
                    run_id,
                    iteration_index,
                    started_at,
                    finished_at,
                    duration_seconds,
                    status,
                    stop_reason,
                    repo_changed,
                    changed_files_count,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    tool_calls_count,
                    test_exit_code,
                    test_timed_out,
                    test_signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.iteration_id,
                    record.run_id,
                    record.iteration_index,
                    record.started_at,
                    record.finished_at,
                    record.duration_seconds,
                    record.status,
                    record.stop_reason,
                    1 if record.repo_changed else 0,
                    record.changed_files_count,
                    record.input_tokens,
                    record.output_tokens,
                    record.total_tokens,
                    record.tool_calls_count,
                    record.test_exit_code,
                    None if record.test_timed_out is None else (1 if record.test_timed_out else 0),
                    record.test_signature,
                ),
            )

    def insert_agent_execution(self, record: AgentExecutionRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO agent_executions (
                    agent_execution_id,
                    run_id,
                    iteration_id,
                    run_agent_id,
                    execution_index,
                    started_at,
                    finished_at,
                    duration_seconds,
                    status,
                    reasoning_summary,
                    confidence,
                    notes,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    tool_calls_count,
                    error_type,
                    error_message_short
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.agent_execution_id,
                    record.run_id,
                    record.iteration_id,
                    record.run_agent_id,
                    record.execution_index,
                    record.started_at,
                    record.finished_at,
                    record.duration_seconds,
                    record.status,
                    record.reasoning_summary,
                    record.confidence,
                    record.notes,
                    record.input_tokens,
                    record.output_tokens,
                    record.total_tokens,
                    record.tool_calls_count,
                    record.error_type,
                    record.error_message_short,
                ),
            )

    def insert_tool_call(self, record: ToolCallRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tool_calls (
                    tool_call_id,
                    run_id,
                    iteration_id,
                    agent_execution_id,
                    seq,
                    tool_name,
                    status,
                    success
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.tool_call_id,
                    record.run_id,
                    record.iteration_id,
                    record.agent_execution_id,
                    record.seq,
                    record.tool_name,
                    record.status,
                    None if record.success is None else (1 if record.success else 0),
                ),
            )

    def insert_test_execution(self, record: TestExecutionRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO test_executions (
                    test_execution_id,
                    run_id,
                    iteration_id,
                    agent_execution_id,
                    tool_call_id,
                    phase,
                    command,
                    duration_seconds,
                    exit_code,
                    timed_out,
                    tests_total,
                    tests_passed,
                    tests_failed,
                    output_path,
                    signature
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.test_execution_id,
                    record.run_id,
                    record.iteration_id,
                    record.agent_execution_id,
                    record.tool_call_id,
                    record.phase,
                    record.command,
                    record.duration_seconds,
                    record.exit_code,
                    None if record.timed_out is None else (1 if record.timed_out else 0),
                    record.tests_total,
                    record.tests_passed,
                    record.tests_failed,
                    record.output_path,
                    record.signature,
                ),
            )

    def insert_file_change(self, record: FileChangeRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO file_changes (
                    file_change_id,
                    run_id,
                    iteration_id,
                    agent_execution_id,
                    tool_call_id,
                    path,
                    change_type,
                    additions,
                    deletions,
                    detected_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.file_change_id,
                    record.run_id,
                    record.iteration_id,
                    record.agent_execution_id,
                    record.tool_call_id,
                    record.path,
                    record.change_type,
                    record.additions,
                    record.deletions,
                    record.detected_by,
                ),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn
