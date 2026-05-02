from __future__ import annotations

import sqlite3
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from llm_autofix_agents.observability.models import (
    AgentDescriptor,
    AgentHandoffRecord,
    IterationRecord,
    ModelConfigDescriptor,
    RunDescriptor,
    ToolCallRecord,
    make_handoff_id,
)
from llm_autofix_agents.observability.sqlite_schema import SCHEMA_VERSION
from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore


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


class SQLiteSchemaV4Tests(unittest.TestCase):
    def _init_store(self, db_path: Path) -> SQLiteObservabilityStore:
        store = SQLiteObservabilityStore(db_path=db_path)
        store.initialize()
        return store

    def test_fresh_install_creates_v4_schema(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "obs.db"
            self._init_store(db_path)
            with sqlite3.connect(db_path) as conn:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
                self.assertEqual(version, SCHEMA_VERSION)
                tables = {
                    row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
                }
                self.assertIn("agent_handoffs", tables)
                cols = {row[1] for row in conn.execute("PRAGMA table_info(tool_calls)").fetchall()}
                self.assertIn("agent_name", cols)

    def test_insert_agent_handoff(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "obs.db"
            store = self._init_store(db_path)
            run_id = "run-handoff-1"
            store.upsert_architecture("multi_agent_handoff")
            model_config_id = store.upsert_model_config(
                ModelConfigDescriptor(
                    provider="ollama", model="qwen2.5-coder:14b", max_turns=3, base_url=None, tracing_disabled=True
                )
            )
            store.insert_run_started(
                descriptor=RunDescriptor(
                    run_id=run_id,
                    architecture="multi_agent_handoff",
                    target_repo=".",
                    target_branch="main",
                    run_fingerprint="abc123",
                ),
                architecture_id=store.upsert_architecture("multi_agent_handoff"),
                started_at="2026-01-01T00:00:00+00:00",
            )
            for order, (name, role) in enumerate([("triage", "triage"), ("localizer", "localizer")], start=1):
                store.upsert_run_agent(
                    run_id=run_id,
                    descriptor=AgentDescriptor(
                        agent_name=name,
                        agent_role=role,
                        model_config=ModelConfigDescriptor(
                            provider="ollama",
                            model="qwen2.5-coder:14b",
                            max_turns=3,
                            base_url=None,
                            tracing_disabled=True,
                        ),
                        tool_profile="minimal",
                        agent_order=order,
                    ),
                    model_config_id=model_config_id,
                )
            iteration_id = f"{run_id}-it01"
            store.insert_iteration(
                IterationRecord(
                    run_id=run_id, iteration_id=iteration_id, iteration_index=1, started_at="2026-01-01T00:00:01+00:00"
                )
            )

            record = AgentHandoffRecord(
                handoff_id=make_handoff_id(run_id, 1, 1),
                run_id=run_id,
                iteration_id=iteration_id,
                from_agent_name="triage",
                to_agent_name="localizer",
                from_run_agent_id="ra-triage",
                to_run_agent_id="ra-localizer",
                occurred_at="2026-01-01T00:00:05+00:00",
            )
            store.insert_agent_handoff(record)

            with sqlite3.connect(db_path) as conn:
                rows = conn.execute("SELECT from_agent_name, to_agent_name FROM agent_handoffs").fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][0], "triage")
                self.assertEqual(rows[0][1], "localizer")

    def test_tool_call_with_agent_name(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "obs.db"
            store = self._init_store(db_path)
            run_id = "run-agent-name-1"
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
                    agent_name="localizer",
                    agent_role="localizer",
                    model_config=ModelConfigDescriptor(
                        provider="ollama", model="test", max_turns=3, base_url=None, tracing_disabled=True
                    ),
                    tool_profile="core",
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
                    tool_call_id=f"{ae_id}-tool001",
                    run_id=run_id,
                    iteration_id=iteration_id,
                    agent_execution_id=ae_id,
                    seq=1,
                    tool_name="search_files",
                    status="success",
                    success=True,
                    agent_name="localizer",
                )
            )

            with sqlite3.connect(db_path) as conn:
                row = conn.execute(
                    "SELECT agent_name FROM tool_calls WHERE tool_call_id = ?", (f"{ae_id}-tool001",)
                ).fetchone()
                self.assertEqual(row[0], "localizer")

    def test_migration_v3_to_v4(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "obs.db"
            conn = sqlite3.connect(db_path)

            v3_tool_calls_sql = """
                CREATE TABLE IF NOT EXISTS tool_calls (
                    tool_call_id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    iteration_id TEXT NOT NULL,
                    agent_execution_id TEXT,
                    seq INTEGER NOT NULL,
                    tool_name TEXT NOT NULL,
                    status TEXT,
                    success INTEGER
                );
            """
            conn.executescript(v3_tool_calls_sql)
            conn.execute("PRAGMA user_version = 3")
            conn.close()

            store = SQLiteObservabilityStore(db_path=db_path)
            store.initialize()

            conn2 = sqlite3.connect(db_path)
            version = conn2.execute("PRAGMA user_version").fetchone()[0]
            self.assertGreaterEqual(version, 4)
            tables = {row[0] for row in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
            self.assertIn("agent_handoffs", tables)
            cols = {row[1] for row in conn2.execute("PRAGMA table_info(tool_calls)").fetchall()}
            self.assertIn("agent_name", cols)
            conn2.close()


class MultiAgentRegistrationTests(unittest.TestCase):
    def test_four_agents_registered_for_handoff(self) -> None:

        from llm_autofix_agents.architectures.config import BuiltArchitecture, SubAgentDescriptor

        architecture = BuiltArchitecture(
            architecture_name="multi_agent_handoff",
            facade_agent_builder=lambda: None,
            agent_name="triage",
            agent_role="triage",
            agent_model="qwen2.5-coder:14b",
            instructions="triage instructions",
            tool_profile="mixed",
            tool_count=4,
            sub_agents=(
                SubAgentDescriptor(
                    agent_name="localizer",
                    agent_role="localizer",
                    model="qwen2.5-coder:14b",
                    instructions="localizer instructions",
                    tool_profile="core",
                ),
                SubAgentDescriptor(
                    agent_name="patcher",
                    agent_role="patcher",
                    model="qwen2.5-coder:14b",
                    instructions="patcher instructions",
                    tool_profile="core",
                ),
                SubAgentDescriptor(
                    agent_name="validator",
                    agent_role="validator",
                    model="qwen2.5-coder:14b",
                    instructions="validator instructions",
                    tool_profile="full",
                ),
            ),
        )

        self.assertEqual(architecture.agent_name, "triage")
        self.assertEqual(len(architecture.sub_agents), 3)
        self.assertEqual(architecture.sub_agents[0].agent_name, "localizer")
        self.assertEqual(architecture.sub_agents[1].agent_name, "patcher")
        self.assertEqual(architecture.sub_agents[2].agent_name, "validator")

    def test_mono_agent_has_empty_sub_agents(self) -> None:
        from llm_autofix_agents.architectures.config import BuiltArchitecture

        architecture = BuiltArchitecture(
            architecture_name="mono_agent",
            facade_agent_builder=lambda: None,
            agent_name="baseline",
            agent_role="fixer",
            instructions="fix instructions",
            tool_profile="full",
            tool_count=12,
        )
        self.assertEqual(len(architecture.sub_agents), 0)


if __name__ == "__main__":
    unittest.main()
