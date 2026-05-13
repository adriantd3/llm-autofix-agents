"""Cross-batch SQLite aggregator CLI.

Usage:
    python -m llm_autofix_agents.observability.aggregate \\
        --out results/analysis.db \\
        results/batch-quixbugs-mono-2026-* \\
        results/batch-handoff-2026-*

Scans each batch directory for batch.db (or run.db files inside run
subdirectories), then merges them into a single analysis DB.

Each invocation overwrites --out from scratch so the result is always
a faithful snapshot of exactly the batch dirs you specified.  Run the
same batch config multiple times and pass all the resulting batch dirs
to register every execution and compute statistics across runs.

The `runs` table gets a `batch_id` column populated from the batch
directory name so you can GROUP BY batch_id for cross-batch comparisons.
"""
from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def _find_dbs_in_batch_dir(batch_dir: Path) -> list[Path]:
    """Return DBs to aggregate from a batch directory.

    Preference order:
      1. batch.db at the batch root (produced by SH5 auto-merge)
      2. All run.db files inside subdirectories (fallback for pre-SH5 batches)
    """
    batch_db = batch_dir / "batch.db"
    if batch_db.exists():
        return [batch_db]
    # Legacy: collect per-run DBs directly
    return sorted(batch_dir.rglob("run.db"))


def aggregate(batch_dirs: list[Path], out_path: Path) -> int:
    """Merge all batch/run DBs into out_path.  Returns total source-DB count.

    Always starts fresh: out_path is deleted before aggregation so the result
    is a clean snapshot of exactly the specified batch dirs.  Pass every batch
    directory you want included — repeated runs of the same config live in
    separate timestamped dirs and will each contribute their own rows.
    """
    import os

    from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        os.remove(out_path)
    dest_store = SQLiteObservabilityStore(db_path=out_path)
    dest_store.initialize()

    total = 0
    for batch_dir in batch_dirs:
        if not batch_dir.is_dir():
            logger.warning("Skipping non-directory: %s", batch_dir)
            continue
        batch_id = batch_dir.name
        dbs = _find_dbs_in_batch_dir(batch_dir)
        if not dbs:
            logger.warning("No DBs found in %s", batch_dir)
            continue
        for db_path in dbs:
            logger.info("Merging %s (batch=%s)", db_path, batch_id)
            dest_store.merge_from(db_path)
            _backfill_batch_id(out_path, db_path, batch_id)
            total += 1

    return total


def _backfill_batch_id(dest_db: Path, src_db: Path, batch_id: str) -> None:
    """Set batch_id on any runs that came from src_db and have no batch_id yet."""
    try:
        # Collect run_ids from src
        with sqlite3.connect(str(src_db)) as src_conn:
            rows = src_conn.execute("SELECT run_id FROM runs").fetchall()
        run_ids = [r[0] for r in rows]
        if not run_ids:
            return
        with sqlite3.connect(str(dest_db)) as dest_conn:
            # Ensure batch_id column exists (added by this aggregator, not in main schema)
            cols = {r[1] for r in dest_conn.execute("PRAGMA table_info(runs)").fetchall()}
            if "batch_id" not in cols:
                dest_conn.execute("ALTER TABLE runs ADD COLUMN batch_id TEXT")
            placeholders = ",".join("?" * len(run_ids))
            dest_conn.execute(
                f"UPDATE runs SET batch_id = ? WHERE run_id IN ({placeholders}) AND batch_id IS NULL",  # noqa: S608
                [batch_id, *run_ids],
            )
    except Exception:
        logger.warning("Failed to backfill batch_id for %s", batch_id, exc_info=True)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description="Aggregate per-batch SQLite DBs into a single analysis DB.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--out", required=True, type=Path, help="Path to write the aggregated DB")
    parser.add_argument("batch_dirs", nargs="+", type=Path, help="Batch result directories to aggregate")
    args = parser.parse_args(argv)

    total = aggregate(args.batch_dirs, args.out)
    print(f"Aggregated {total} source DB(s) into {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
