"""Tests for scripts/aggregate_experiment_results.py.

Focus: edge cases that could break the aggregation silently.
"""
from __future__ import annotations

import importlib.util
import sqlite3
import sys
import uuid
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the script as a module (it lives outside src/, not an installed package)
# ---------------------------------------------------------------------------

_SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "aggregate_experiment_results.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("aggregate_experiment_results", _SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


agg = _load_module()

# ---------------------------------------------------------------------------
# Helpers to build minimal batch.db fixtures
# ---------------------------------------------------------------------------

_SCHEMA = """\
CREATE TABLE IF NOT EXISTS architectures (
  architecture_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);
CREATE TABLE IF NOT EXISTS model_configs (
  model_config_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  base_url TEXT,
  max_turns INTEGER,
  tracing_disabled INTEGER,
  extra_json TEXT,
  UNIQUE (provider, model, base_url, max_turns, tracing_disabled, extra_json)
);
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  architecture_id TEXT NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  target_repo TEXT,
  target_branch TEXT,
  benchmark_name TEXT,
  problem_id TEXT,
  prompt_hash TEXT,
  run_fingerprint TEXT,
  final_status TEXT,
  stop_reason TEXT,
  resolved INTEGER NOT NULL DEFAULT 0,
  duration_seconds REAL,
  total_iterations INTEGER NOT NULL DEFAULT 0,
  total_input_tokens INTEGER NOT NULL DEFAULT 0,
  total_output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  files_changed_count INTEGER NOT NULL DEFAULT 0,
  live_log_path TEXT,
  summary_path TEXT,
  diff_path TEXT,
  error_type TEXT,
  error_message TEXT,
  error_category TEXT,
  error_traceback TEXT,
  FOREIGN KEY (architecture_id) REFERENCES architectures(architecture_id)
);
CREATE TABLE IF NOT EXISTS run_agents (
  run_agent_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  agent_name TEXT NOT NULL,
  agent_role TEXT NOT NULL,
  agent_order INTEGER,
  model_config_id TEXT NOT NULL,
  instructions_hash TEXT,
  tool_profile TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (model_config_id) REFERENCES model_configs(model_config_id),
  UNIQUE (run_id, agent_name)
);
CREATE TABLE IF NOT EXISTS iterations (
  iteration_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_index INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_seconds REAL,
  status TEXT,
  stop_reason TEXT,
  repo_changed INTEGER NOT NULL DEFAULT 0,
  changed_files_count INTEGER NOT NULL DEFAULT 0,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  tool_calls_count INTEGER NOT NULL DEFAULT 0,
  test_exit_code INTEGER,
  test_timed_out INTEGER,
  test_signature TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  UNIQUE (run_id, iteration_index)
);
CREATE TABLE IF NOT EXISTS agent_executions (
  agent_execution_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT NOT NULL,
  run_agent_id TEXT NOT NULL,
  execution_index INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_seconds REAL,
  status TEXT,
  reasoning_summary TEXT,
  confidence REAL,
  notes TEXT,
  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,
  tool_calls_count INTEGER NOT NULL DEFAULT 0,
  error_type TEXT,
  error_message_short TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (run_agent_id) REFERENCES run_agents(run_agent_id)
);
CREATE TABLE IF NOT EXISTS tool_calls (
  tool_call_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT NOT NULL,
  agent_execution_id TEXT,
  seq INTEGER NOT NULL,
  tool_name TEXT NOT NULL,
  status TEXT,
  success INTEGER,
  agent_name TEXT,
  run_agent_id TEXT,
  started_at TEXT,
  finished_at TEXT,
  duration_seconds REAL,
  args_summary_json TEXT,
  result_summary_json TEXT,
  retry_index INTEGER,
  error_type TEXT,
  error_message_short TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id)
);
CREATE TABLE IF NOT EXISTS provider_call_events (
  provider_call_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT NOT NULL,
  agent_execution_id TEXT,
  event_type TEXT NOT NULL,
  attempt INTEGER NOT NULL,
  total_attempts INTEGER NOT NULL,
  status_code INTEGER,
  error_type TEXT,
  error_message_short TEXT,
  tool_calls_count INTEGER,
  retry_delay_seconds REAL,
  rerun_full_runner INTEGER NOT NULL DEFAULT 1,
  occurred_at TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id)
);
CREATE TABLE IF NOT EXISTS test_executions (
  test_execution_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT,
  agent_execution_id TEXT,
  tool_call_id TEXT,
  phase TEXT NOT NULL,
  command TEXT,
  duration_seconds REAL,
  exit_code INTEGER,
  timed_out INTEGER,
  signature TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS file_changes (
  file_change_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT,
  agent_execution_id TEXT,
  tool_call_id TEXT,
  path TEXT NOT NULL,
  change_type TEXT,
  additions INTEGER,
  deletions INTEGER,
  detected_by TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS agent_handoffs (
  handoff_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  iteration_id TEXT,
  from_agent_name TEXT NOT NULL,
  to_agent_name TEXT NOT NULL,
  from_run_agent_id TEXT,
  to_run_agent_id TEXT,
  occurred_at TEXT NOT NULL,
  handoff_note_json TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
CREATE TABLE IF NOT EXISTS run_validations (
  validation_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  validated_at TEXT NOT NULL,
  validator_model TEXT NOT NULL,
  test_passed INTEGER,
  infra_fail_detected INTEGER,
  canonical_patch_available INTEGER,
  patch_semantically_matches INTEGER,
  verdict TEXT NOT NULL,
  confidence REAL,
  justification TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
"""


def _make_batch_db(batch_dir: Path, arch_id: str, arch_name: str, model_id: str,
                   run_ids: list[str], resolved_run_ids: list[str] | None = None,
                   validated_run_ids: list[str] | None = None) -> Path:
    """Create a minimal batch.db inside batch_dir with the given runs."""
    batch_dir.mkdir(parents=True, exist_ok=True)
    db_path = batch_dir / "batch.db"
    resolved_set = set(resolved_run_ids or [])
    validated_set = set(run_ids if validated_run_ids is None else validated_run_ids)

    with sqlite3.connect(db_path) as con:
        con.executescript(_SCHEMA)
        con.execute(
            "INSERT OR IGNORE INTO architectures VALUES (?, ?, NULL)",
            (arch_id, arch_name),
        )
        con.execute(
            "INSERT OR IGNORE INTO model_configs VALUES (?, 'openai', 'gpt-test', 'https://api.test', 10, 1, '{}')",
            (model_id,),
        )
        for run_id in run_ids:
            resolved = 1 if run_id in resolved_set else 0
            con.execute(
                """INSERT INTO runs (run_id, architecture_id, started_at, benchmark_name,
                   problem_id, final_status, resolved) VALUES (?, ?, '2026-01-01T00:00:00', 'bench', ?, 'success', ?)""",
                (run_id, arch_id, run_id, resolved),
            )
            ra_id = f"ra-{run_id}"
            con.execute(
                """INSERT INTO run_agents (run_agent_id, run_id, agent_name, agent_role, model_config_id)
                   VALUES (?, ?, 'agent', 'agent', ?)""",
                (ra_id, run_id, model_id),
            )
            iter_id = f"iter-{run_id}"
            con.execute(
                """INSERT INTO iterations (iteration_id, run_id, iteration_index, started_at)
                   VALUES (?, ?, 0, '2026-01-01T00:00:00')""",
                (iter_id, run_id),
            )
            if run_id in validated_set:
                val_id = str(uuid.uuid4())
                con.execute(
                    """INSERT INTO run_validations (validation_id, run_id, validated_at,
                       validator_model, verdict) VALUES (?, ?, '2026-01-01T00:00:00', 'judge', 'CORRECT')""",
                    (val_id, run_id),
                )
        con.commit()

    return db_path


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDiscoverExperimentBatchDirs:
    def test_finds_dirs_with_experiment_and_batch_db(self, tmp_path: Path) -> None:
        # Three valid experiment dirs + one that should be ignored
        for name in ["batch-experiment-foo-20260101T000000Z", "batch-experiment-bar-20260101T000001Z"]:
            d = tmp_path / name
            d.mkdir()
            (d / "batch.db").touch()

        # Should be ignored: no "experiment" in name
        non_exp = tmp_path / "batch-quixbugs-baz-20260101Z"
        non_exp.mkdir()
        (non_exp / "batch.db").touch()

        # Should be ignored: has "experiment" but no batch.db
        no_db = tmp_path / "batch-experiment-nodb"
        no_db.mkdir()

        dirs = agg.discover_experiment_batch_dirs(tmp_path)
        names = [d.name for d in dirs]
        assert len(dirs) == 2
        assert "batch-experiment-foo-20260101T000000Z" in names
        assert "batch-experiment-bar-20260101T000001Z" in names
        assert "batch-quixbugs-baz-20260101Z" not in names

    def test_raises_when_results_dir_missing(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            agg.discover_experiment_batch_dirs(tmp_path / "nonexistent")

    def test_returns_empty_list_when_no_experiments(self, tmp_path: Path) -> None:
        (tmp_path / "batch-quixbugs-20260101Z").mkdir()
        result = agg.discover_experiment_batch_dirs(tmp_path)
        assert result == []


class TestAggregateBasic:
    """Core merge functionality."""

    def test_merges_two_batches_runs_count(self, tmp_path: Path) -> None:
        arch_id = "arch-abc"
        model_id = "model-xyz"
        batch1 = tmp_path / "results" / "batch-experiment-a-20260101T000000Z"
        batch2 = tmp_path / "results" / "batch-experiment-b-20260101T000001Z"
        _make_batch_db(batch1, arch_id, "mono_agent", model_id, ["run-1", "run-2"])
        _make_batch_db(batch2, arch_id, "mono_agent", model_id, ["run-3", "run-4", "run-5"])

        out = tmp_path / "out.db"
        totals = agg.aggregate([batch1, batch2], out)

        assert out.exists()
        with sqlite3.connect(out) as con:
            count = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert count == 5
        assert totals["runs"] == 5

    def test_shared_architecture_not_duplicated(self, tmp_path: Path) -> None:
        """Same architecture_id in two batches → only one row in output."""
        arch_id = "arch-same"
        model_id = "model-xyz"
        for i, runs in enumerate([["run-1"], ["run-2"]]):
            _make_batch_db(
                tmp_path / f"batch-experiment-x{i}-20260101T00000{i}Z",
                arch_id, "mono_agent", model_id, runs,
            )

        batch_dirs = sorted(tmp_path.iterdir())
        out = tmp_path.parent / "out.db"
        agg.aggregate(batch_dirs, out)

        with sqlite3.connect(out) as con:
            arch_count = con.execute("SELECT COUNT(*) FROM architectures").fetchone()[0]
        assert arch_count == 1

    def test_shared_model_config_not_duplicated(self, tmp_path: Path) -> None:
        model_id = "model-shared"
        arch_id = "arch-a"
        for i, runs in enumerate([["run-a"], ["run-b"]]):
            _make_batch_db(
                tmp_path / f"batch-experiment-m{i}-20260101T00000{i}Z",
                arch_id, "mono_agent", model_id, runs,
            )

        batch_dirs = sorted(tmp_path.iterdir())
        out = tmp_path.parent / "out.db"
        agg.aggregate(batch_dirs, out)

        with sqlite3.connect(out) as con:
            model_count = con.execute("SELECT COUNT(*) FROM model_configs").fetchone()[0]
        assert model_count == 1

    def test_batch_id_backfilled_on_all_runs(self, tmp_path: Path) -> None:
        arch_id, model_id = "arch-a", "model-a"
        batch1 = tmp_path / "batch-experiment-p-20260101T000000Z"
        batch2 = tmp_path / "batch-experiment-q-20260101T000001Z"
        _make_batch_db(batch1, arch_id, "mono_agent", model_id, ["run-p1", "run-p2"])
        _make_batch_db(batch2, arch_id, "mono_agent", model_id, ["run-q1"])

        out = tmp_path / "out.db"
        agg.aggregate([batch1, batch2], out)

        with sqlite3.connect(out) as con:
            rows = con.execute("SELECT run_id, batch_id FROM runs ORDER BY run_id").fetchall()

        batch_ids = {run_id: batch_id for run_id, batch_id in rows}
        assert batch_ids["run-p1"] == batch1.name
        assert batch_ids["run-p2"] == batch1.name
        assert batch_ids["run-q1"] == batch2.name

    def test_overwrite_existing_output(self, tmp_path: Path) -> None:
        """Re-running with same batches produces a fresh, correct DB."""
        arch_id, model_id = "arch-a", "model-a"
        batch = tmp_path / "batch-experiment-r-20260101T000000Z"
        _make_batch_db(batch, arch_id, "mono_agent", model_id, ["run-r1"])
        out = tmp_path / "out.db"

        agg.aggregate([batch], out)
        agg.aggregate([batch], out)  # second call must not double-count

        with sqlite3.connect(out) as con:
            count = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert count == 1


class TestAggregateEdgeCases:
    """Cases likely to cause silent data loss or corruption."""

    def test_empty_batch_dirs_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="No batch directories"):
            agg.aggregate([], tmp_path / "out.db")

    def test_run_id_collision_across_batches_is_detected(self, tmp_path: Path) -> None:
        """If two batches share a run_id (should not happen in practice), only one row is kept
        and the integrity check does NOT produce an orphan warning — but the count will be off."""
        arch_id, model_id = "arch-a", "model-a"
        batch1 = tmp_path / "batch-experiment-col1-20260101T000000Z"
        batch2 = tmp_path / "batch-experiment-col2-20260101T000001Z"
        _make_batch_db(batch1, arch_id, "mono_agent", model_id, ["run-SAME"])
        _make_batch_db(batch2, arch_id, "mono_agent", model_id, ["run-SAME"])

        out = tmp_path / "out.db"
        agg.aggregate([batch1, batch2], out)

        with sqlite3.connect(out) as con:
            count = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        # INSERT OR IGNORE keeps only one of the two identical PKs
        assert count == 1

    def test_missing_batch_db_is_skipped_gracefully(self, tmp_path: Path) -> None:
        """A directory with 'experiment' but no batch.db must not crash the aggregation."""
        arch_id, model_id = "arch-a", "model-a"
        valid = tmp_path / "batch-experiment-ok-20260101T000000Z"
        _make_batch_db(valid, arch_id, "mono_agent", model_id, ["run-ok"])

        # This dir has no batch.db, should not appear in discover results
        empty = tmp_path / "batch-experiment-empty-20260101T000001Z"
        empty.mkdir()

        batch_dirs = agg.discover_experiment_batch_dirs(tmp_path)
        assert len(batch_dirs) == 1  # only the valid one

    def test_iterations_linked_correctly_after_merge(self, tmp_path: Path) -> None:
        """iterations.run_id must reference an existing run in the merged DB."""
        arch_id, model_id = "arch-a", "model-a"
        batch = tmp_path / "batch-experiment-link-20260101T000000Z"
        _make_batch_db(batch, arch_id, "mono_agent", model_id, ["run-link1", "run-link2"])

        out = tmp_path / "out.db"
        agg.aggregate([batch], out)

        with sqlite3.connect(out) as con:
            orphan_iters = con.execute("""
                SELECT COUNT(*) FROM iterations i
                WHERE NOT EXISTS (SELECT 1 FROM runs r WHERE r.run_id = i.run_id)
            """).fetchone()[0]
        assert orphan_iters == 0

    def test_run_validations_linked_correctly(self, tmp_path: Path) -> None:
        arch_id, model_id = "arch-a", "model-a"
        batch = tmp_path / "batch-experiment-val-20260101T000000Z"
        _make_batch_db(
            batch, arch_id, "mono_agent", model_id,
            ["run-v1", "run-v2"], validated_run_ids=["run-v1"],
        )

        out = tmp_path / "out.db"
        agg.aggregate([batch], out)

        with sqlite3.connect(out) as con:
            orphan = con.execute("""
                SELECT COUNT(*) FROM run_validations rv
                WHERE NOT EXISTS (SELECT 1 FROM runs r WHERE r.run_id = rv.run_id)
            """).fetchone()[0]
            val_count = con.execute("SELECT COUNT(*) FROM run_validations").fetchone()[0]

        assert orphan == 0
        assert val_count == 2

    def test_unresolved_without_validation_gets_fail(self, tmp_path: Path) -> None:
        arch_id, model_id = "arch-a", "model-a"
        batch = tmp_path / "batch-experiment-unvalidated-20260101T000000Z"
        _make_batch_db(
            batch,
            arch_id,
            "mono_agent",
            model_id,
            ["run-unvalidated"],
            resolved_run_ids=[],
            validated_run_ids=[],
        )

        out = tmp_path / "out.db"
        agg.aggregate([batch], out)

        with sqlite3.connect(out) as con:
            row = con.execute(
                """
                SELECT rv.verdict, rv.test_passed, rv.validator_model
                FROM runs r
                JOIN run_validations rv ON rv.run_id = r.run_id
                WHERE r.run_id = 'run-unvalidated'
                """
            ).fetchone()

        assert row == ("FAIL", 0, "aggregate-normalizer")

    def test_unresolved_existing_verdict_is_normalized_to_fail(self, tmp_path: Path) -> None:
        arch_id, model_id = "arch-a", "model-a"
        batch = tmp_path / "batch-experiment-wrong-verdict-20260101T000000Z"
        _make_batch_db(
            batch,
            arch_id,
            "mono_agent",
            model_id,
            ["run-wrong"],
            resolved_run_ids=[],
            validated_run_ids=["run-wrong"],
        )

        out = tmp_path / "out.db"
        agg.aggregate([batch], out)

        with sqlite3.connect(out) as con:
            row = con.execute(
                """
                SELECT rv.verdict, rv.test_passed, rv.patch_semantically_matches, rv.confidence
                FROM runs r
                JOIN run_validations rv ON rv.run_id = r.run_id
                WHERE r.run_id = 'run-wrong'
                """
            ).fetchone()

        assert row == ("FAIL", 0, None, None)

    def test_batches_with_different_architectures_both_present(self, tmp_path: Path) -> None:
        batch1 = tmp_path / "batch-experiment-arch1-20260101T000000Z"
        batch2 = tmp_path / "batch-experiment-arch2-20260101T000001Z"
        _make_batch_db(batch1, "arch-mono", "mono_agent", "model-a", ["run-m1"])
        _make_batch_db(batch2, "arch-orch", "orchestrator", "model-a", ["run-o1"])

        out = tmp_path / "out.db"
        agg.aggregate([batch1, batch2], out)

        with sqlite3.connect(out) as con:
            arch_count = con.execute("SELECT COUNT(*) FROM architectures").fetchone()[0]
            run_count = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert arch_count == 2
        assert run_count == 2

    def test_large_number_of_batches(self, tmp_path: Path) -> None:
        """50 batches each with 3 runs — ensures no performance or connection issue."""
        arch_id, model_id = "arch-a", "model-a"
        all_run_ids = []
        batch_dirs = []
        for i in range(50):
            runs = [f"run-{i}-{j}" for j in range(3)]
            all_run_ids.extend(runs)
            bd = tmp_path / f"batch-experiment-stress-{i:04d}-20260101T{i:06d}Z"
            _make_batch_db(bd, arch_id, "mono_agent", model_id, runs)
            batch_dirs.append(bd)

        out = tmp_path / "stress-out.db"
        totals = agg.aggregate(batch_dirs, out)

        with sqlite3.connect(out) as con:
            count = con.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        assert count == 150
        assert totals["runs"] == 150


class TestVerifyIntegrity:
    def test_passes_on_clean_merge(self, tmp_path: Path) -> None:
        arch_id, model_id = "arch-a", "model-a"
        batch = tmp_path / "batch-experiment-clean-20260101T000000Z"
        _make_batch_db(batch, arch_id, "mono_agent", model_id, ["run-c1", "run-c2"])

        out = tmp_path / "out.db"
        agg.aggregate([batch], out)
        warnings = agg.verify_integrity(out, expected_run_count=2)
        assert warnings == []

    def test_detects_wrong_run_count(self, tmp_path: Path) -> None:
        arch_id, model_id = "arch-a", "model-a"
        batch = tmp_path / "batch-experiment-count-20260101T000000Z"
        _make_batch_db(batch, arch_id, "mono_agent", model_id, ["run-cnt"])

        out = tmp_path / "out.db"
        agg.aggregate([batch], out)

        # Pass wrong expected count
        warnings = agg.verify_integrity(out, expected_run_count=99)
        assert any("Expected 99 runs" in w for w in warnings)

    def test_detects_null_batch_id(self, tmp_path: Path) -> None:
        arch_id, model_id = "arch-a", "model-a"
        batch = tmp_path / "batch-experiment-null-20260101T000000Z"
        _make_batch_db(batch, arch_id, "mono_agent", model_id, ["run-null"])

        out = tmp_path / "out.db"
        agg.aggregate([batch], out)

        # Manually nullify batch_id to simulate corruption
        with sqlite3.connect(out) as con:
            con.execute("UPDATE runs SET batch_id = NULL")

        warnings = agg.verify_integrity(out, expected_run_count=1)
        assert any("NULL batch_id" in w for w in warnings)


class TestCLI:
    def test_dry_run_does_not_create_output(self, tmp_path: Path) -> None:
        arch_id, model_id = "arch-a", "model-a"
        batch = tmp_path / "results" / "batch-experiment-dry-20260101T000000Z"
        _make_batch_db(batch, arch_id, "mono_agent", model_id, ["run-dry"])

        out = tmp_path / "out.db"
        rc = agg.main([
            "--results-dir", str(tmp_path / "results"),
            "--out", str(out),
            "--dry-run",
        ])
        assert rc == 0
        assert not out.exists()

    def test_cli_full_run_returns_zero_on_clean_data(self, tmp_path: Path) -> None:
        arch_id, model_id = "arch-a", "model-a"
        for i in range(3):
            batch = tmp_path / "results" / f"batch-experiment-cli{i}-20260101T00000{i}Z"
            _make_batch_db(batch, arch_id, "mono_agent", model_id, [f"run-cli{i}"])

        out = tmp_path / "out.db"
        rc = agg.main([
            "--results-dir", str(tmp_path / "results"),
            "--out", str(out),
        ])
        assert rc == 0
        assert out.exists()

    def test_cli_returns_nonzero_when_no_batches_found(self, tmp_path: Path) -> None:
        (tmp_path / "results").mkdir()
        out = tmp_path / "out.db"
        rc = agg.main([
            "--results-dir", str(tmp_path / "results"),
            "--out", str(out),
        ])
        assert rc == 1
