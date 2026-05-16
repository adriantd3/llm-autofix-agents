from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from llm_autofix_agents.observability.models import RunValidationRecord
from llm_autofix_agents.observability.sqlite_schema import SCHEMA_VERSION
from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore


def _make_store(tmp_dir: Path) -> SQLiteObservabilityStore:
    store = SQLiteObservabilityStore(db_path=tmp_dir / "test.db")
    store.initialize()
    return store


def _insert_minimal_run(db_path: Path, run_id: str) -> None:
    """Insert the minimum set of rows needed to satisfy FK constraints for a run."""
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(
            "INSERT INTO architectures (architecture_id, name) VALUES (?, ?)",
            ("arch-test", "test-arch"),
        )
        conn.execute(
            "INSERT INTO runs (run_id, architecture_id, started_at, benchmark_name, problem_id)"
            " VALUES (?, ?, datetime('now'), ?, ?)",
            (run_id, "arch-test", "quixbugs", "gcd"),
        )


class TestSchemaVersion(unittest.TestCase):
    def test_version_is_7(self) -> None:
        self.assertEqual(SCHEMA_VERSION, 7)

    def test_fresh_db_has_run_validations_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(Path(tmp))
            with sqlite3.connect(str(store.db_path)) as conn:
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertIn("run_validations", tables)

    def test_fresh_db_user_version_is_7(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(Path(tmp))
            with sqlite3.connect(str(store.db_path)) as conn:
                version = conn.execute("PRAGMA user_version").fetchone()[0]
            self.assertEqual(version, 7)


class TestUpsertRunValidation(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._store = _make_store(Path(self._tmp.name))
        self._run_id = "run-test-001"
        _insert_minimal_run(self._store.db_path, self._run_id)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _make_record(self, verdict: str = "CORRECT", validation_id: str = "val-0001") -> RunValidationRecord:
        return RunValidationRecord(
            validation_id=validation_id,
            run_id=self._run_id,
            validated_at="2026-05-16T00:00:00+00:00",
            validator_model="gpt-4.1-mini",
            verdict=verdict,
            test_passed=True,
            infra_fail_detected=False,
            canonical_patch_available=True,
            patch_semantically_matches=True,
            confidence=0.9,
            justification="The fix addresses the root cause correctly.",
        )

    def test_insert_verdict(self) -> None:
        record = self._make_record()
        self._store.upsert_run_validation(record)

        with sqlite3.connect(str(self._store.db_path)) as conn:
            row = conn.execute(
                "SELECT verdict, confidence, justification FROM run_validations WHERE run_id = ?",
                (self._run_id,),
            ).fetchone()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], "CORRECT")
        self.assertAlmostEqual(row[1], 0.9)
        self.assertIn("root cause", row[2])

    def test_upsert_overwrites_verdict(self) -> None:
        self._store.upsert_run_validation(self._make_record(verdict="INCORRECT"))
        self._store.upsert_run_validation(self._make_record(verdict="CORRECT"))

        with sqlite3.connect(str(self._store.db_path)) as conn:
            rows = conn.execute("SELECT verdict FROM run_validations WHERE run_id = ?", (self._run_id,)).fetchall()

        self.assertEqual(len(rows), 1, "upsert should not create duplicate rows")
        self.assertEqual(rows[0][0], "CORRECT")

    def test_bool_fields_stored_as_integers(self) -> None:
        record = self._make_record()
        self._store.upsert_run_validation(record)

        with sqlite3.connect(str(self._store.db_path)) as conn:
            row = conn.execute(
                "SELECT test_passed, infra_fail_detected, canonical_patch_available, patch_semantically_matches"
                " FROM run_validations WHERE run_id = ?",
                (self._run_id,),
            ).fetchone()

        self.assertEqual(row[0], 1)   # test_passed
        self.assertEqual(row[1], 0)   # infra_fail_detected
        self.assertEqual(row[2], 1)   # canonical_patch_available
        self.assertEqual(row[3], 1)   # patch_semantically_matches

    def test_nullable_fields_accept_none(self) -> None:
        record = RunValidationRecord(
            validation_id="val-null",
            run_id=self._run_id,
            validated_at="2026-05-16T00:00:00+00:00",
            validator_model="gpt-4.1-mini",
            verdict="INFRA_FAIL",
        )
        self._store.upsert_run_validation(record)

        with sqlite3.connect(str(self._store.db_path)) as conn:
            row = conn.execute(
                "SELECT test_passed, patch_semantically_matches, confidence, justification"
                " FROM run_validations WHERE run_id = ?",
                (self._run_id,),
            ).fetchone()

        self.assertIsNone(row[0])
        self.assertIsNone(row[1])
        self.assertIsNone(row[2])
        self.assertIsNone(row[3])


class TestMergeFromPreservesValidations(unittest.TestCase):
    def test_merge_copies_run_validations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            src_path = Path(tmp) / "src.db"
            dst_path = Path(tmp) / "dst.db"

            src_store = SQLiteObservabilityStore(db_path=src_path)
            src_store.initialize()
            _insert_minimal_run(src_path, "run-src-001")
            src_store.upsert_run_validation(
                RunValidationRecord(
                    validation_id="val-src-001",
                    run_id="run-src-001",
                    validated_at="2026-05-16T00:00:00+00:00",
                    validator_model="gpt-4.1-mini",
                    verdict="PLAUSIBLE",
                )
            )

            dst_store = SQLiteObservabilityStore(db_path=dst_path)
            dst_store.initialize()
            dst_store.merge_from(src_path)

            with sqlite3.connect(str(dst_path)) as conn:
                row = conn.execute("SELECT verdict FROM run_validations WHERE run_id = ?", ("run-src-001",)).fetchone()

            self.assertIsNotNone(row)
            self.assertEqual(row[0], "PLAUSIBLE")


class TestCreateAnalysisViews(unittest.TestCase):
    def test_views_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(Path(tmp))
            store.create_analysis_views()

            with sqlite3.connect(str(store.db_path)) as conn:
                views = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='view'")}

            self.assertIn("v_run_summary", views)
            self.assertIn("v_architecture_metrics", views)
            self.assertIn("v_bug_heatmap", views)


if __name__ == "__main__":
    unittest.main()
