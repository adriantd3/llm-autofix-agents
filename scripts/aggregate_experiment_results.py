#!/usr/bin/env python3
"""aggregate_experiment_results.py — Merge all experiment batch DBs into one.

Discovers every ``batch-experiment-*`` directory under ``results/`` that
contains a ``batch.db`` file and merges them into a single SQLite database
suitable for cross-batch statistical analysis.

The output DB preserves the full schema of the individual batch DBs and adds
one extra column:

- ``runs.batch_id``  – set to the batch directory name for each run, so you
  can always trace a row back to its originating batch.

Usage
─────
    uv run python scripts/aggregate_experiment_results.py
    uv run python scripts/aggregate_experiment_results.py --out results/my_analysis.db
    uv run python scripts/aggregate_experiment_results.py --results-dir /path/to/results

Flags
─────
    --out PATH          Destination DB path.
                        Default: results/experiment-aggregate-<TIMESTAMP>.db
    --results-dir DIR   Directory to scan for batch-experiment-* subdirs.
                        Default: results/ relative to the repo root.
    --dry-run           List discovered batch dirs without writing anything.
    --verbose           Emit DEBUG logging.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Ordered list of tables to merge; insertion order respects FK dependencies.
_TABLES = [
    "architectures",
    "model_configs",
    "runs",
    "run_agents",
    "iterations",
    "agent_executions",
    "tool_calls",
    "provider_call_events",
    "test_executions",
    "file_changes",
    "agent_handoffs",
    "run_validations",
]

_FAIL_VALIDATOR_MODEL = "aggregate-normalizer"
_FAIL_JUSTIFICATION = "Run did not pass tests; semantic validation is not applicable."


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def discover_experiment_batch_dirs(results_dir: Path) -> list[Path]:
    """Return sorted list of experiment batch dirs that contain a batch.db."""
    if not results_dir.is_dir():
        raise FileNotFoundError(f"results_dir not found: {results_dir}")

    dirs = sorted(
        d
        for d in results_dir.iterdir()
        if d.is_dir()
        and "experiment" in d.name
        and (d / "batch.db").exists()
    )
    return dirs


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------


def _ensure_batch_id_column(conn: sqlite3.Connection) -> None:
    """Add batch_id column to runs if it does not already exist."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(runs)")}
    if "batch_id" not in cols:
        conn.execute("ALTER TABLE runs ADD COLUMN batch_id TEXT")


def _create_schema_from_source(dest_conn: sqlite3.Connection, src_db: Path) -> None:
    """Replicate the table schema from src_db into dest_conn (skipping existing tables)."""
    with sqlite3.connect(src_db) as src:
        ddl_rows = src.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
        ).fetchall()

    existing = {row[0] for row in dest_conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}

    for name, ddl in ddl_rows:
        if name not in existing:
            dest_conn.execute(ddl)
            logger.debug("Created table %s", name)


# ---------------------------------------------------------------------------
# Merge logic
# ---------------------------------------------------------------------------


def _merge_batch_db(dest_conn: sqlite3.Connection, src_db: Path, batch_id: str) -> dict[str, int]:
    """Merge one batch.db into dest_conn.

    Returns a dict of {table_name: rows_inserted} for reporting.
    """
    inserted: dict[str, int] = {}

    dest_conn.execute(f"ATTACH DATABASE '{src_db}' AS src")
    try:
        for table in _TABLES:
            # Determine columns present in both source and destination.
            dest_cols = {row[1] for row in dest_conn.execute(f"PRAGMA table_info({table})")}
            src_cols_rows = dest_conn.execute(f"PRAGMA src.table_info({table})").fetchall()

            if not src_cols_rows:
                logger.debug("Table %s not found in %s — skipping", table, src_db)
                continue

            src_cols = [row[1] for row in src_cols_rows]
            common = [c for c in src_cols if c in dest_cols]
            if not common:
                logger.debug("No common columns for %s — skipping", table)
                continue

            col_list = ", ".join(common)
            before = dest_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            dest_conn.execute(
                f"INSERT OR IGNORE INTO {table} ({col_list}) SELECT {col_list} FROM src.{table}"  # noqa: S608
            )
            after = dest_conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
            inserted[table] = after - before

        # Backfill batch_id on runs that came from this batch and have no batch_id yet.
        run_ids = [row[0] for row in dest_conn.execute("SELECT run_id FROM src.runs").fetchall()]
        if run_ids:
            placeholders = ",".join("?" * len(run_ids))
            dest_conn.execute(
                f"UPDATE runs SET batch_id = ? WHERE run_id IN ({placeholders}) AND batch_id IS NULL",  # noqa: S608
                [batch_id, *run_ids],
            )

        # Commit before detaching: SQLite forbids DETACH while an open
        # transaction still references the attached database.
        dest_conn.commit()

    finally:
        dest_conn.execute("DETACH DATABASE src")

    return inserted


# ---------------------------------------------------------------------------
# Main aggregation entry point
# ---------------------------------------------------------------------------


def aggregate(
    batch_dirs: list[Path],
    out_path: Path,
) -> dict[str, int]:
    """Merge all batch_dirs into a fresh SQLite DB at out_path.

    Always starts from scratch (existing out_path is removed) to produce a
    deterministic, reproducible result.

    Returns cumulative row-insertion counts per table.
    """
    if not batch_dirs:
        raise ValueError("No batch directories provided.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        logger.info("Removing existing output DB: %s", out_path)
        out_path.unlink()

    totals: dict[str, int] = {t: 0 for t in _TABLES}

    # Bootstrap schema from the first available batch DB.
    first_db = batch_dirs[0] / "batch.db"
    with sqlite3.connect(out_path) as conn:
        conn.execute("PRAGMA foreign_keys = OFF")  # OFF during bulk load
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")

        _create_schema_from_source(conn, first_db)
        _ensure_batch_id_column(conn)

    # Merge each batch DB.
    for batch_dir in batch_dirs:
        src_db = batch_dir / "batch.db"
        batch_id = batch_dir.name
        logger.info("Merging %s", batch_id)

        with sqlite3.connect(out_path) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            counts = _merge_batch_db(conn, src_db, batch_id)
            conn.commit()

        for table, n in counts.items():
            totals[table] += n
            if n:
                logger.debug("  %s: +%d rows", table, n)

    with sqlite3.connect(out_path) as conn:
        normalized_failures = _normalize_failed_run_validations(conn)
        totals["run_validations"] += normalized_failures
        conn.commit()
    logger.info("Normalized %d unresolved run(s) as FAIL", normalized_failures)

    # Re-enable FK enforcement for reads.
    with sqlite3.connect(out_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")

    logger.info("Aggregation complete → %s", out_path)
    return totals


def _normalize_failed_run_validations(conn: sqlite3.Connection) -> int:
    """Ensure every unresolved run has a FAIL validation verdict.

    Source batch DBs are preserved as raw experimental artefacts. The aggregate
    DB is the analysis surface, so it receives a clean, explicit verdict for
    every run that did not pass the test signal.
    """
    validated_at = datetime.now(tz=timezone.utc).isoformat()

    before = conn.execute("SELECT COUNT(*) FROM run_validations").fetchone()[0]
    conn.execute(
        """
        UPDATE run_validations
        SET verdict = 'FAIL',
            test_passed = 0,
            patch_semantically_matches = NULL,
            confidence = NULL
        WHERE run_id IN (SELECT run_id FROM runs WHERE resolved = 0)
        """
    )
    conn.execute(
        """
        INSERT INTO run_validations (
            validation_id,
            run_id,
            validated_at,
            validator_model,
            test_passed,
            infra_fail_detected,
            canonical_patch_available,
            patch_semantically_matches,
            verdict,
            confidence,
            justification
        )
        SELECT
            'fail-' || r.run_id,
            r.run_id,
            ?,
            ?,
            0,
            NULL,
            NULL,
            NULL,
            'FAIL',
            NULL,
            ?
        FROM runs r
        WHERE r.resolved = 0
          AND NOT EXISTS (
              SELECT 1 FROM run_validations rv WHERE rv.run_id = r.run_id
          )
        """,
        (validated_at, _FAIL_VALIDATOR_MODEL, _FAIL_JUSTIFICATION),
    )
    after = conn.execute("SELECT COUNT(*) FROM run_validations").fetchone()[0]
    return after - before


# ---------------------------------------------------------------------------
# Integrity verification
# ---------------------------------------------------------------------------


def verify_integrity(out_path: Path, expected_run_count: int) -> list[str]:
    """Run basic sanity checks on the aggregated DB.

    Returns a list of warning strings (empty = all clear).
    """
    warnings: list[str] = []

    with sqlite3.connect(out_path) as conn:
        actual_runs = conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0]
        if actual_runs != expected_run_count:
            warnings.append(
                f"Expected {expected_run_count} runs, found {actual_runs}"
            )

        # Every run must have a batch_id.
        null_batch = conn.execute(
            "SELECT COUNT(*) FROM runs WHERE batch_id IS NULL"
        ).fetchone()[0]
        if null_batch:
            warnings.append(f"{null_batch} run(s) have NULL batch_id")

        # run_validations must all reference existing runs.
        orphan_validations = conn.execute("""
            SELECT COUNT(*) FROM run_validations rv
            WHERE NOT EXISTS (SELECT 1 FROM runs r WHERE r.run_id = rv.run_id)
        """).fetchone()[0]
        if orphan_validations:
            warnings.append(f"{orphan_validations} run_validation(s) reference missing runs")

        invalid_verdicts = conn.execute("""
            SELECT COUNT(*)
            FROM run_validations
            WHERE verdict NOT IN ('CORRECT', 'PLAUSIBLE', 'OVERFITTING', 'FAIL')
        """).fetchone()[0]
        if invalid_verdicts:
            warnings.append(f"{invalid_verdicts} invalid validation verdict(s) remain")

        unresolved_non_fail = conn.execute("""
            SELECT COUNT(*)
            FROM run_validations rv
            JOIN runs r ON r.run_id = rv.run_id
            WHERE r.resolved = 0 AND rv.verdict <> 'FAIL'
        """).fetchone()[0]
        if unresolved_non_fail:
            warnings.append(f"{unresolved_non_fail} unresolved validation(s) are not FAIL")

        unresolved_without_fail = conn.execute("""
            SELECT COUNT(*)
            FROM runs r
            WHERE r.resolved = 0
              AND NOT EXISTS (
                  SELECT 1 FROM run_validations rv
                  WHERE rv.run_id = r.run_id AND rv.verdict = 'FAIL'
              )
        """).fetchone()[0]
        if unresolved_without_fail:
            warnings.append(f"{unresolved_without_fail} unresolved run(s) lack FAIL validation")

        # iterations must all reference existing runs.
        orphan_iters = conn.execute("""
            SELECT COUNT(*) FROM iterations i
            WHERE NOT EXISTS (SELECT 1 FROM runs r WHERE r.run_id = i.run_id)
        """).fetchone()[0]
        if orphan_iters:
            warnings.append(f"{orphan_iters} iteration(s) reference missing runs")

        # Unique (run_id, iteration_index) within iterations.
        dup_iters = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT run_id, iteration_index, COUNT(*) AS n
                FROM iterations
                GROUP BY run_id, iteration_index
                HAVING n > 1
            )
        """).fetchone()[0]
        if dup_iters:
            warnings.append(f"{dup_iters} duplicate (run_id, iteration_index) pairs in iterations")

    return warnings


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def print_summary(out_path: Path) -> None:
    """Print a brief textual summary of the aggregated DB to stdout."""
    with sqlite3.connect(out_path) as conn:
        tables = _TABLES + ["runs"]  # runs listed separately in body
        row_counts = {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]  # noqa: S608
            for t in _TABLES
        }

        print("\n=== Aggregated DB summary ===")
        print(f"File: {out_path}")
        print()
        for t, n in row_counts.items():
            print(f"  {t:<30} {n:>8} rows")

        print()
        # Per-architecture breakdown
        arch_rows = conn.execute("""
            SELECT a.name, COUNT(r.run_id) AS total_runs,
                   SUM(r.resolved) AS resolved,
                   COUNT(rv.validation_id) AS validated
            FROM architectures a
            JOIN runs r ON r.architecture_id = a.architecture_id
            LEFT JOIN run_validations rv ON rv.run_id = r.run_id
            GROUP BY a.name
            ORDER BY a.name
        """).fetchall()
        if arch_rows:
            print("  Per architecture:")
            for name, total, resolved, validated in arch_rows:
                pct = f"{100*resolved/total:.1f}%" if total else "n/a"
                print(f"    {name:<35} runs={total:>4}  resolved={resolved:>3} ({pct})  validated={validated:>3}")

        print()
        # Per-model breakdown
        model_rows = conn.execute("""
            SELECT mc.model, COUNT(DISTINCT r.run_id) AS runs,
                   SUM(r.resolved) AS resolved
            FROM model_configs mc
            JOIN run_agents ra ON ra.model_config_id = mc.model_config_id
            JOIN runs r ON r.run_id = ra.run_id
            GROUP BY mc.model
            ORDER BY mc.model
        """).fetchall()
        if model_rows:
            print("  Per model:")
            for model, runs, resolved in model_rows:
                pct = f"{100*resolved/runs:.1f}%" if runs else "n/a"
                print(f"    {model:<35} runs={runs:>4}  resolved={resolved:>3} ({pct})")

        print()
        # Verdict breakdown (from run_validations)
        verdict_rows = conn.execute("""
            SELECT verdict, COUNT(*) AS n
            FROM run_validations
            GROUP BY verdict
            ORDER BY n DESC
        """).fetchall()
        if verdict_rows:
            print("  Validation verdicts:")
            for verdict, n in verdict_rows:
                print(f"    {verdict:<20} {n:>5}")

        print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_default_out_path(results_dir: Path) -> Path:
    ts = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return results_dir / f"experiment-aggregate-{ts}.db"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Aggregate all batch-experiment-* SQLite DBs into one.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output DB path (default: results/experiment-aggregate-<TIMESTAMP>.db)",
    )
    parser.add_argument(
        "--results-dir",
        type=Path,
        default=None,
        help="Directory to scan for batch-experiment-* dirs (default: <repo>/results)",
    )
    parser.add_argument("--dry-run", action="store_true", help="List batches without writing")
    parser.add_argument("--verbose", action="store_true", help="Enable DEBUG logging")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    repo_root = Path(__file__).resolve().parent.parent
    results_dir = args.results_dir or (repo_root / "results")
    out_path = args.out or _build_default_out_path(results_dir)

    # --- Discover ---
    logger.info("Scanning %s for experiment batches …", results_dir)
    batch_dirs = discover_experiment_batch_dirs(results_dir)

    if not batch_dirs:
        logger.error("No experiment batch directories with batch.db found in %s", results_dir)
        return 1

    logger.info("Found %d experiment batch(es)", len(batch_dirs))

    if args.dry_run:
        print(f"Would merge {len(batch_dirs)} batch(es) into {out_path}:")
        for d in batch_dirs:
            print(f"  {d.name}")
        return 0

    # Count total source runs for integrity check later.
    expected_run_count = 0
    for bd in batch_dirs:
        with sqlite3.connect(bd / "batch.db") as c:
            expected_run_count += c.execute("SELECT COUNT(*) FROM runs").fetchone()[0]

    # --- Merge ---
    totals = aggregate(batch_dirs, out_path)

    # --- Integrity check ---
    warnings = verify_integrity(out_path, expected_run_count)
    if warnings:
        logger.warning("Integrity warnings:")
        for w in warnings:
            logger.warning("  %s", w)
    else:
        logger.info("Integrity check passed.")

    # --- Summary ---
    print_summary(out_path)

    inserted_runs = totals.get("runs", 0)
    print(f"Merged {len(batch_dirs)} batch(es) — {inserted_runs} runs written to {out_path}")

    return 1 if warnings else 0


if __name__ == "__main__":
    sys.exit(main())
