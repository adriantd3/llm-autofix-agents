from __future__ import annotations

import json
import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from llm_autofix_agents.observability.interactive import MarkdownLiveObserver
from llm_autofix_agents.observability.jsonl_observer import JsonlEventObserver
from llm_autofix_agents.observability.models import (
    AgentDescriptor,
    AgentHandoffRecord,
    APRHandoffNote,
    FacadeInputRecord,
    IterationRecord,
    ModelConfigDescriptor,
    RunDescriptor,
    RunFinishedRecord,
    ToolCallRecord,
    make_handoff_id,
)
from llm_autofix_agents.observability.sqlite_schema import SCHEMA_VERSION
from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore
from llm_autofix_agents.observability.tool_summaries import (
    summarize_tool_args,
    summarize_tool_result,
)


class AgentHandoffRecordTests(unittest.TestCase):
    def test_make_handoff_id(self) -> None:
        hid = make_handoff_id("run-1", 1, 2)
        self.assertEqual(hid, "run-1-it01-handoff002")

    def test_handoff_record_creation(self) -> None:
        record = AgentHandoffRecord(
            handoff_id="run-1-it01-handoff001",
            run_id="run-1",
            iteration_id="run-1-it01",
            from_agent_name="triage",
            to_agent_name="localizer",
            from_run_agent_id="ra-triage",
            to_run_agent_id="ra-localizer",
            occurred_at="2026-01-01T00:00:00+00:00",
        )
        self.assertEqual(record.from_agent_name, "triage")
        self.assertEqual(record.to_agent_name, "localizer")
        self.assertIsNone(record.handoff_note_json)

    def test_handoff_record_with_note(self) -> None:
        note_dict = {"summary": "Bug in gcd", "suspected_files": ["gcd.py"]}
        record = AgentHandoffRecord(
            handoff_id="run-1-it01-handoff001",
            run_id="run-1",
            iteration_id="run-1-it01",
            from_agent_name="triage",
            to_agent_name="localizer",
            from_run_agent_id="ra-triage",
            to_run_agent_id="ra-localizer",
            occurred_at="2026-01-01T00:00:00+00:00",
            handoff_note_json=json.dumps(note_dict),
        )
        self.assertEqual(record.from_agent_name, "triage")
        parsed = json.loads(record.handoff_note_json)
        self.assertEqual(parsed["summary"], "Bug in gcd")


class APRHandoffNoteTests(unittest.TestCase):
    def test_handoff_note_creation(self) -> None:
        note = APRHandoffNote(
            summary="Bug is in gcd function",
            evidence=["test fails on edge case"],
            suspected_files=["gcd.py"],
            next_focus="gcd function logic",
            confidence=0.85,
        )
        self.assertEqual(note.summary, "Bug is in gcd function")
        self.assertEqual(note.suspected_files, ["gcd.py"])
        self.assertEqual(note.confidence, 0.85)

    def test_handoff_note_minimal(self) -> None:
        note = APRHandoffNote(
            summary="Found it",
            evidence=[],
            suspected_files=[],
        )
        self.assertEqual(note.summary, "Found it")
        self.assertIsNone(note.next_focus)
        self.assertIsNone(note.confidence)


class ToolCallRecordTests(unittest.TestCase):
    def test_enriched_record_with_all_fields(self) -> None:
        record = ToolCallRecord(
            tool_call_id="tc-abc123def456",
            run_id="run-1",
            iteration_id="run-1-it01",
            agent_execution_id="run-1-it01-agent01",
            seq=1,
            tool_name="read_file",
            status="success",
            success=True,
            agent_name="baseline",
            run_agent_id="ra-baseline",
            started_at="2026-01-01T00:00:01+00:00",
            finished_at="2026-01-01T00:00:02+00:00",
            duration_seconds=1.0,
            args_summary_json='{"path":"foo.py"}',
            result_summary_json='{"ok":true,"path":"foo.py"}',
            result_excerpt='{"ok":true,',
            error_type=None,
            error_message_short=None,
        )
        self.assertEqual(record.tool_call_id, "tc-abc123def456")
        self.assertEqual(record.duration_seconds, 1.0)
        self.assertEqual(record.agent_name, "baseline")

    def test_backward_compatible_record(self) -> None:
        record = ToolCallRecord(
            tool_call_id="tc-old",
            run_id="run-1",
            iteration_id="run-1-it01",
            agent_execution_id="run-1-it01-agent01",
            seq=1,
            tool_name="read_file",
            status="success",
            success=True,
        )
        self.assertIsNone(record.duration_seconds)
        self.assertIsNone(record.result_summary_json)
        self.assertIsNone(record.agent_name)


class ToolSummariesTests(unittest.TestCase):
    def test_summarize_read_file_success(self) -> None:
        result = json.dumps(
            {
                "ok": True,
                "path": "gcd.py",
                "start_line": 1,
                "end_line": 50,
                "line_count": 50,
                "truncated": False,
                "content": "x" * 200,
            }
        )
        summary = summarize_tool_result("read_file", result)
        self.assertEqual(summary["ok"], True)
        self.assertEqual(summary["path"], "gcd.py")
        self.assertEqual(summary["line_count"], 50)
        self.assertIn("content_hash", summary)
        self.assertEqual(summary["content_chars"], 200)

    def test_summarize_read_file_error(self) -> None:
        result = json.dumps({"ok": False, "error": "file_not_found", "path": "missing.py"})
        summary = summarize_tool_result("read_file", result)
        self.assertEqual(summary["ok"], False)
        self.assertEqual(summary["error"], "file_not_found")

    def test_summarize_replace_in_file_success(self) -> None:
        result = json.dumps({"ok": True, "path": "gcd.py", "replaced": 1, "bytes_written": 500})
        summary = summarize_tool_result("replace_in_file", result)
        self.assertEqual(summary["ok"], True)
        self.assertEqual(summary["replaced"], 1)

    def test_summarize_execute_command(self) -> None:
        result = json.dumps(
            {
                "ok": True,
                "command": "pytest gcd.py",
                "exit_code": 0,
                "timed_out": False,
                "stdout": "x" * 300,
                "stderr": "",
                "cwd": ".",
            }
        )
        summary = summarize_tool_result("execute_command", result)
        self.assertEqual(summary["exit_code"], 0)
        self.assertIn("stdout_chars", summary)

    def test_summarize_invalid_json(self) -> None:
        summary = summarize_tool_result("read_file", "not json at all")
        self.assertIsNone(summary["ok"])

    def test_summarize_tool_args_replace_in_file(self) -> None:
        args = {"path": "gcd.py", "old": "x" * 1000, "new": "y" * 500, "replace_all": False}
        summary = summarize_tool_args("replace_in_file", args)
        self.assertEqual(summary["path"], "gcd.py")
        self.assertIn("old_hash", summary)
        self.assertIn("new_hash", summary)
        self.assertNotIn("old", summary)

    def test_summarize_tool_args_write_file(self) -> None:
        args = {"path": "new.py", "content": "x" * 5000, "create_dirs": True}
        summary = summarize_tool_args("write_file", args)
        self.assertEqual(summary["content_length"], 5000)
        self.assertNotIn("content", summary)


class SQLiteSchemaV5Tests(unittest.TestCase):
    def _init_store(self, db_path: Path) -> SQLiteObservabilityStore:
        store = SQLiteObservabilityStore(db_path=db_path)
        store.initialize()
        return store

    def test_fresh_install_creates_v5_schema(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "obs.db"
            self._init_store(db_path)
            with sqlite3.connect(db_path) as conn:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                self.assertEqual(version, SCHEMA_VERSION)
                tool_cols = {row[1] for row in conn.execute("PRAGMA table_info(tool_calls)").fetchall()}
                for col in [
                    "run_agent_id",
                    "started_at",
                    "finished_at",
                    "duration_seconds",
                    "args_summary_json",
                    "result_summary_json",
                    "result_excerpt",
                    "error_type",
                    "error_message_short",
                ]:
                    self.assertIn(col, tool_cols, f"Missing column: {col}")
                handoff_cols = {row[1] for row in conn.execute("PRAGMA table_info(agent_handoffs)").fetchall()}
                self.assertIn("handoff_note_json", handoff_cols)

    def test_insert_enriched_tool_call(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "obs.db"
            store = self._init_store(db_path)
            run_id = "run-enriched-1"
            arch_id = store.upsert_architecture("mono_agent")
            model_id = store.upsert_model_config(
                ModelConfigDescriptor(
                    provider="ollama", model="test", max_turns=3, base_url=None, tracing_disabled=True
                )
            )
            store.insert_run_started(
                descriptor=RunDescriptor(
                    run_id=run_id,
                    architecture="mono_agent",
                    target_repo=".",
                    target_branch="main",
                    run_fingerprint="abc",
                ),
                architecture_id=arch_id,
                started_at="2026-01-01T00:00:00+00:00",
            )
            ra_id = store.upsert_run_agent(
                run_id=run_id,
                descriptor=AgentDescriptor(
                    agent_name="baseline",
                    agent_role="fixer",
                    model_config=ModelConfigDescriptor(
                        provider="ollama", model="test", max_turns=3, base_url=None, tracing_disabled=True
                    ),
                    tool_profile="full",
                    agent_order=1,
                ),
                model_config_id=model_id,
            )
            iteration_id = f"{run_id}-it01"
            store.insert_iteration(
                IterationRecord(
                    run_id=run_id, iteration_id=iteration_id, iteration_index=1, started_at="2026-01-01T00:00:01+00:00"
                )
            )
            from llm_autofix_agents.observability.models import AgentExecutionRecord

            ae_id = f"{run_id}-it01-agent01"
            store.insert_agent_execution(
                AgentExecutionRecord.started(
                    agent_execution_id=ae_id,
                    run_id=run_id,
                    iteration_id=iteration_id,
                    run_agent_id=ra_id,
                    execution_index=1,
                )
            )

            store.insert_tool_call(
                ToolCallRecord(
                    tool_call_id="tc-enriched001",
                    run_id=run_id,
                    iteration_id=iteration_id,
                    agent_execution_id=ae_id,
                    seq=1,
                    tool_name="read_file",
                    status="success",
                    success=True,
                    agent_name="baseline",
                    run_agent_id=ra_id,
                    started_at="2026-01-01T00:00:02+00:00",
                    finished_at="2026-01-01T00:00:03+00:00",
                    duration_seconds=1.0,
                    args_summary_json='{"path":"gcd.py","start_line":1,"end_line":50}',
                    result_summary_json='{"ok":true,"path":"gcd.py","line_count":50}',
                    result_excerpt='{"ok":true,',
                    error_type=None,
                    error_message_short=None,
                )
            )

            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT run_agent_id, started_at, finished_at, duration_seconds, args_summary_json, result_summary_json FROM tool_calls WHERE tool_call_id = ?",
                    ("tc-enriched001",),
                ).fetchone()
                self.assertEqual(row[0], ra_id)
                self.assertEqual(row[1], "2026-01-01T00:00:02+00:00")
                self.assertAlmostEqual(row[3], 1.0)
                self.assertIn("gcd.py", row[4])
                self.assertIn("gcd.py", row[5])

    def test_migration_v4_to_v5(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "obs.db"

            v3_schema = """
                PRAGMA foreign_keys = ON;
                CREATE TABLE IF NOT EXISTS architectures (architecture_id TEXT PRIMARY KEY, name TEXT NOT NULL UNIQUE, description TEXT);
                CREATE TABLE IF NOT EXISTS model_configs (model_config_id TEXT PRIMARY KEY, provider TEXT NOT NULL, model TEXT NOT NULL, base_url TEXT, max_turns INTEGER, tracing_disabled INTEGER, extra_json TEXT);
                CREATE TABLE IF NOT EXISTS runs (run_id TEXT PRIMARY KEY, architecture_id TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, target_repo TEXT, target_branch TEXT, benchmark_name TEXT, problem_id TEXT, prompt_hash TEXT, run_fingerprint TEXT, final_status TEXT, stop_reason TEXT, resolved INTEGER NOT NULL DEFAULT 0, duration_seconds REAL, total_iterations INTEGER NOT NULL DEFAULT 0, total_input_tokens INTEGER NOT NULL DEFAULT 0, total_output_tokens INTEGER NOT NULL DEFAULT 0, total_tokens INTEGER NOT NULL DEFAULT 0, files_changed_count INTEGER NOT NULL DEFAULT 0, live_log_path TEXT, summary_path TEXT, diff_path TEXT);
                CREATE TABLE IF NOT EXISTS run_agents (run_agent_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, agent_name TEXT NOT NULL, agent_role TEXT NOT NULL, agent_order INTEGER, model_config_id TEXT NOT NULL, instructions_hash TEXT, tool_profile TEXT);
                CREATE TABLE IF NOT EXISTS iterations (iteration_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, iteration_index INTEGER NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, duration_seconds REAL, status TEXT, stop_reason TEXT, repo_changed INTEGER NOT NULL DEFAULT 0, changed_files_count INTEGER NOT NULL DEFAULT 0, input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0, total_tokens INTEGER NOT NULL DEFAULT 0, tool_calls_count INTEGER NOT NULL DEFAULT 0, test_exit_code INTEGER, test_timed_out INTEGER, test_signature TEXT);
                CREATE TABLE IF NOT EXISTS agent_executions (agent_execution_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, iteration_id TEXT NOT NULL, run_agent_id TEXT NOT NULL, execution_index INTEGER NOT NULL, started_at TEXT NOT NULL, finished_at TEXT, duration_seconds REAL, status TEXT, reasoning_summary TEXT, confidence REAL, notes TEXT, input_tokens INTEGER NOT NULL DEFAULT 0, output_tokens INTEGER NOT NULL DEFAULT 0, total_tokens INTEGER NOT NULL DEFAULT 0, tool_calls_count INTEGER NOT NULL DEFAULT 0, error_type TEXT, error_message_short TEXT);
                CREATE TABLE IF NOT EXISTS tool_calls (tool_call_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, iteration_id TEXT NOT NULL, agent_execution_id TEXT, seq INTEGER NOT NULL, tool_name TEXT NOT NULL, status TEXT, success INTEGER, agent_name TEXT);
                CREATE TABLE IF NOT EXISTS provider_call_events (provider_call_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, iteration_id TEXT NOT NULL, agent_execution_id TEXT, event_type TEXT NOT NULL, attempt INTEGER NOT NULL, total_attempts INTEGER NOT NULL, status_code INTEGER, error_type TEXT, error_message_short TEXT, tool_calls_count INTEGER, retry_delay_seconds REAL, rerun_full_runner INTEGER NOT NULL DEFAULT 1, occurred_at TEXT);
                CREATE TABLE IF NOT EXISTS test_executions (test_execution_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, iteration_id TEXT, agent_execution_id TEXT, tool_call_id TEXT, phase TEXT NOT NULL, command TEXT, duration_seconds REAL, exit_code INTEGER, timed_out INTEGER, signature TEXT);
                CREATE TABLE IF NOT EXISTS file_changes (file_change_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, iteration_id TEXT, agent_execution_id TEXT, tool_call_id TEXT, path TEXT NOT NULL, change_type TEXT, additions INTEGER, deletions INTEGER, detected_by TEXT);
                CREATE INDEX IF NOT EXISTS idx_runs_architecture ON runs(architecture_id);
                CREATE INDEX IF NOT EXISTS idx_iterations_run ON iterations(run_id);
                CREATE INDEX IF NOT EXISTS idx_agent_executions_run_agent ON agent_executions(run_agent_id);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id);
                CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(tool_name);
                CREATE INDEX IF NOT EXISTS idx_provider_call_events_run ON provider_call_events(run_id);
                CREATE INDEX IF NOT EXISTS idx_provider_call_events_agent_execution ON provider_call_events(agent_execution_id);
                CREATE TABLE IF NOT EXISTS agent_handoffs (handoff_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, iteration_id TEXT, from_agent_name TEXT NOT NULL, to_agent_name TEXT NOT NULL, from_run_agent_id TEXT, to_run_agent_id TEXT, occurred_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS idx_agent_handoffs_run ON agent_handoffs(run_id);
                CREATE INDEX IF NOT EXISTS idx_agent_handoffs_iteration ON agent_handoffs(iteration_id);
            """
            conn = sqlite3.connect(db_path)
            conn.executescript(v3_schema)
            conn.execute("PRAGMA user_version = 4")
            conn.close()

            store = SQLiteObservabilityStore(db_path=db_path)
            store.initialize()

            conn2 = sqlite3.connect(db_path)
            version = conn2.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, SCHEMA_VERSION)
            tool_cols = {row[1] for row in conn2.execute("PRAGMA table_info(tool_calls)").fetchall()}
            self.assertIn("duration_seconds", tool_cols)
            self.assertIn("result_summary_json", tool_cols)
            self.assertIn("args_summary_json", tool_cols)
            handoff_cols = {row[1] for row in conn2.execute("PRAGMA table_info(agent_handoffs)").fetchall()}
            self.assertIn("handoff_note_json", handoff_cols)
            conn2.close()

    def test_insert_handoff_with_note(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "obs.db"
            store = self._init_store(db_path)
            run_id = "run-handoff-note-1"
            store.upsert_architecture("multi_agent_handoff")
            model_id = store.upsert_model_config(
                ModelConfigDescriptor(
                    provider="ollama", model="test", max_turns=3, base_url=None, tracing_disabled=True
                )
            )
            store.insert_run_started(
                descriptor=RunDescriptor(
                    run_id=run_id,
                    architecture="multi_agent_handoff",
                    target_repo=".",
                    target_branch="main",
                    run_fingerprint="abc",
                ),
                architecture_id=store.upsert_architecture("multi_agent_handoff"),
                started_at="2026-01-01T00:00:00+00:00",
            )
            for name, role in [("triage", "triage"), ("localizer", "localizer")]:
                store.upsert_run_agent(
                    run_id=run_id,
                    descriptor=AgentDescriptor(
                        agent_name=name,
                        agent_role=role,
                        model_config=ModelConfigDescriptor(
                            provider="ollama", model="test", max_turns=3, base_url=None, tracing_disabled=True
                        ),
                        tool_profile="minimal",
                        agent_order=1,
                    ),
                    model_config_id=model_id,
                )
            iteration_id = f"{run_id}-it01"
            store.insert_iteration(
                IterationRecord(
                    run_id=run_id, iteration_id=iteration_id, iteration_index=1, started_at="2026-01-01T00:00:01+00:00"
                )
            )

            note_json = json.dumps({"summary": "Bug in gcd", "suspected_files": ["gcd.py"], "confidence": 0.85})
            record = AgentHandoffRecord(
                handoff_id=make_handoff_id(run_id, 1, 1),
                run_id=run_id,
                iteration_id=iteration_id,
                from_agent_name="triage",
                to_agent_name="localizer",
                from_run_agent_id="ra-triage",
                to_run_agent_id="ra-localizer",
                occurred_at="2026-01-01T00:00:05+00:00",
                handoff_note_json=note_json,
            )
            store.insert_agent_handoff(record)

            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT from_agent_name, to_agent_name, handoff_note_json FROM agent_handoffs"
                ).fetchone()
                self.assertEqual(row[0], "triage")
                self.assertEqual(row[1], "localizer")
                parsed = json.loads(row[2])
                self.assertEqual(parsed["summary"], "Bug in gcd")
                self.assertEqual(parsed["confidence"], 0.85)


class JsonlEventObserverTests(unittest.TestCase):
    def test_jsonl_observer_writes_valid_json_lines(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            results_dir = Path(tmp_dir)
            observer = JsonlEventObserver(results_dir, "run-jsonl-1")

            observer.on_run_started(
                run=RunDescriptor(
                    run_id="run-jsonl-1",
                    architecture="mono_agent",
                    target_repo=".",
                    target_branch="main",
                    run_fingerprint="abc123",
                ),
                started_at="2026-01-01T00:00:00+00:00",
            )
            observer.on_tool_call(
                record=ToolCallRecord(
                    tool_call_id="tc-test001",
                    run_id="run-jsonl-1",
                    iteration_id="run-jsonl-1-it01",
                    agent_execution_id="run-jsonl-1-it01-agent01",
                    seq=1,
                    tool_name="read_file",
                    status="success",
                    success=True,
                    agent_name="baseline",
                    duration_seconds=0.5,
                )
            )
            observer.on_agent_handoff(
                record=AgentHandoffRecord(
                    handoff_id="run-jsonl-1-it01-handoff001",
                    run_id="run-jsonl-1",
                    iteration_id="run-jsonl-1-it01",
                    from_agent_name="triage",
                    to_agent_name="localizer",
                    from_run_agent_id=None,
                    to_run_agent_id=None,
                    occurred_at="2026-01-01T00:00:05+00:00",
                    handoff_note_json='{"summary":"Bug found"}',
                )
            )
            observer.on_run_finished(
                run_finished=RunFinishedRecord(
                    run_id="run-jsonl-1",
                    finished_at="2026-01-01T00:00:10+00:00",
                    final_status="success",
                    stop_reason="completed",
                    duration_seconds=10.0,
                    total_iterations=1,
                    total_input_tokens=100,
                    total_output_tokens=200,
                    total_tokens=300,
                    files_changed_count=1,
                    resolved=True,
                )
            )

            content = observer.path.read_text(encoding="utf-8")
            lines = [line for line in content.strip().split("\n") if line]
            self.assertEqual(len(lines), 4)

            events = [json.loads(line) for line in lines]
            self.assertEqual(events[0]["event"], "run_started")
            self.assertEqual(events[0]["run_id"], "run-jsonl-1")

            self.assertEqual(events[1]["event"], "tool_call")
            self.assertEqual(events[1]["tool_name"], "read_file")
            self.assertAlmostEqual(events[1]["duration_seconds"], 0.5)

            self.assertEqual(events[2]["event"], "agent_handoff")
            self.assertEqual(events[2]["from_agent_name"], "triage")
            self.assertEqual(events[2]["handoff_note_json"], '{"summary":"Bug found"}')

            self.assertEqual(events[3]["event"], "run_finished")
            self.assertEqual(events[3]["final_status"], "success")


class MarkdownLiveObserverEnrichedTests(unittest.TestCase):
    def test_tool_call_shows_agent_and_duration(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            live_path = Path(tmp_dir) / "results" / "run-enriched" / "live.md"
            observer = MarkdownLiveObserver(live_path)

            observer.on_run_started(
                run=RunDescriptor(
                    run_id="run-enriched",
                    architecture="mono_agent",
                    target_repo=".",
                    target_branch="main",
                    run_fingerprint="abc",
                ),
                started_at="2026-01-01T00:00:00+00:00",
            )
            observer.on_tool_call(
                record=ToolCallRecord(
                    tool_call_id="tc-001",
                    run_id="run-enriched",
                    iteration_id="run-enriched-it01",
                    agent_execution_id="run-enriched-it01-agent01",
                    seq=1,
                    tool_name="read_file",
                    status="success",
                    success=True,
                    agent_name="patcher",
                    duration_seconds=0.007,
                )
            )
            observer.on_tool_call(
                record=ToolCallRecord(
                    tool_call_id="tc-002",
                    run_id="run-enriched",
                    iteration_id="run-enriched-it01",
                    agent_execution_id="run-enriched-it01-agent01",
                    seq=2,
                    tool_name="replace_in_file",
                    status="success",
                    success=True,
                    agent_name="patcher",
                    duration_seconds=1.234,
                )
            )
            observer.on_tool_call(
                record=ToolCallRecord(
                    tool_call_id="tc-003",
                    run_id="run-enriched",
                    iteration_id="run-enriched-it01",
                    agent_execution_id="run-enriched-it01-agent01",
                    seq=3,
                    tool_name="execute_command",
                    status="success",
                    success=True,
                    agent_name=None,
                    duration_seconds=None,
                )
            )

            content = live_path.read_text(encoding="utf-8")
            self.assertIn("[patcher] read_file -> success (0.007s)", content)
            self.assertIn("[patcher] replace_in_file -> success (1.234s)", content)
            self.assertIn("execute_command -> success", content)

    def test_handoff_shows_note(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            live_path = Path(tmp_dir) / "results" / "run-note" / "live.md"
            observer = MarkdownLiveObserver(live_path)

            observer.on_agent_handoff(
                record=AgentHandoffRecord(
                    handoff_id="run-note-it01-handoff001",
                    run_id="run-note",
                    iteration_id="run-note-it01",
                    from_agent_name="triage",
                    to_agent_name="localizer",
                    from_run_agent_id=None,
                    to_run_agent_id=None,
                    occurred_at="2026-01-01T00:00:05+00:00",
                    handoff_note_json=json.dumps(
                        {
                            "summary": "Bug in gcd calculation",
                            "suspected_files": ["gcd.py"],
                            "confidence": 0.85,
                        }
                    ),
                )
            )

            content = live_path.read_text(encoding="utf-8")
            self.assertIn("handoff: triage -> localizer", content)
            self.assertIn("summary: Bug in gcd calculation", content)
            self.assertIn("suspected_files: [", content)
            self.assertIn("confidence: 0.85", content)


class FacadeInputRecordTests(unittest.TestCase):
    def test_facade_input_record_creation(self) -> None:
        record = FacadeInputRecord(
            run_id="run-1",
            iteration_id="run-1-it01",
            iteration_index=1,
            input_text="Fix the parser",
            occurred_at="2026-01-01T00:00:00+00:00",
        )
        self.assertEqual(record.run_id, "run-1")
        self.assertEqual(record.input_text, "Fix the parser")


class JsonlFacadeInputTests(unittest.TestCase):
    def test_jsonl_observer_writes_facade_input(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            results_dir = Path(tmp_dir)
            observer = JsonlEventObserver(results_dir, "run-jsonl-input")

            observer.on_facade_input(
                record=FacadeInputRecord(
                    run_id="run-jsonl-input",
                    iteration_id="run-jsonl-input-it01",
                    iteration_index=1,
                    input_text="Fix the parser failure\n- step 1\n- step 2",
                    occurred_at="2026-01-01T00:00:01+00:00",
                )
            )

            content = observer.path.read_text(encoding="utf-8")
            lines = [line for line in content.strip().split("\n") if line]
            self.assertEqual(len(lines), 1)

            event = json.loads(lines[0])
            self.assertEqual(event["event"], "facade_input")
            self.assertEqual(event["run_id"], "run-jsonl-input")
            self.assertEqual(event["iteration_index"], 1)
            self.assertIn("step 1", event["input_text"])


class MarkdownLiveFacadeInputTests(unittest.TestCase):
    def test_facade_input_shows_full_text_in_code_block(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            live_path = Path(tmp_dir) / "results" / "run-input" / "live.md"
            observer = MarkdownLiveObserver(live_path)

            observer.on_facade_input(
                record=FacadeInputRecord(
                    run_id="run-input",
                    iteration_id="run-input-it02",
                    iteration_index=2,
                    input_text="line1\nline2\nline3",
                    occurred_at="2026-01-01T00:00:00+00:00",
                )
            )

            content = live_path.read_text(encoding="utf-8")
            self.assertIn("### Facade input (iteration 2)", content)
            self.assertIn("```", content)
            self.assertIn("line1", content)
            self.assertIn("line2", content)
            self.assertIn("line3", content)


if __name__ == "__main__":
    unittest.main()
