#!/usr/bin/env python3
"""
validate_batch.py — Persistence layer for APR batch validation verdicts.

This script has two modes:

1. List mode (--list-runs):
   Query the batch DB and return a JSON array with the resolved runs that
   still need validation. The agent reads this to know what to process.

2. Write mode (default, reads from stdin):
   Accept a JSON array of verdicts produced by the agent and write them
   to the run_validations table. The agent is the judge; this script only
   persists.

The agent (not this script) is responsible for analyzing patches and producing
verdicts following the apr-validator skill protocol (steps 1–6).

Usage:
    # Step 1 — list runs needing validation
    uv run python .agents/skills/apr-validator/scripts/validate_batch.py \\
        --db results/batch.db --list-runs

    # Step 2 — persist verdicts produced by the agent (JSON array via stdin)
    echo '[{"run_id": "...", "verdict": "CORRECT", ...}]' | \\
    uv run python .agents/skills/apr-validator/scripts/validate_batch.py \\
        --db results/batch.db

    # List a specific run (e.g. to re-validate)
    uv run python .agents/skills/apr-validator/scripts/validate_batch.py \\
        --db results/batch.db --list-runs --run-id run-20260517T121942Z-ab8baf311e

    # Force re-listing already-validated runs
    uv run python .agents/skills/apr-validator/scripts/validate_batch.py \\
        --db results/batch.db --list-runs --force
"""

import argparse
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


# ── Path helpers ──────────────────────────────────────────────────────────────

def _repo_root_from_db(db_path: Path) -> Path:
    """Infer the project REPO_ROOT from the batch DB path.

    DB is always at results/batch-experiment-<name>/batch.db relative to
    the repo root, so REPO_ROOT = db_path.resolve().parent.parent.parent.
    """
    return db_path.resolve().parent.parent.parent


def _resolve_host_path(path: str | None, repo_root: Path) -> str | None:
    """Translate container-internal absolute paths to host-accessible paths.

    Experiments run inside Docker with volume mounts:
      /results/          → {repo_root}/results/
      /benchmark-workspaces/ → not available on host (omit)
    """
    if not path:
        return path
    if path.startswith("/results/"):
        return str(repo_root / "results" / path[len("/results/"):])
    return path


# ── DB helpers ────────────────────────────────────────────────────────────────

def fetch_runs(
    conn: sqlite3.Connection,
    force: bool,
    run_id: str | None,
    repo_root: Path,
) -> list[dict]:
    """Query resolved runs eligible for (re-)validation."""
    query = """
        SELECT r.run_id, r.target_repo, r.live_log_path, r.diff_path,
               r.benchmark_name, r.problem_id, a.name AS arch
        FROM runs r
        JOIN architectures a ON a.architecture_id = r.architecture_id
        WHERE r.resolved = 1
          AND r.live_log_path IS NOT NULL
    """
    params: list = []

    if run_id:
        query += " AND r.run_id = ?"
        params.append(run_id)
    elif not force:
        query += " AND r.run_id NOT IN (SELECT run_id FROM run_validations)"

    conn.row_factory = sqlite3.Row
    runs = [dict(row) for row in conn.execute(query, params).fetchall()]

    # Translate container paths to host-accessible paths
    for run in runs:
        run["live_log_path"] = _resolve_host_path(run.get("live_log_path"), repo_root)
        run["diff_path"] = _resolve_host_path(run.get("diff_path"), repo_root)

    return runs


def write_validation(conn: sqlite3.Connection, run_id: str, result: dict) -> None:
    """Upsert a single verdict into run_validations."""
    patch_matches_raw = result.get("patch_semantically_matches")
    if patch_matches_raw is True:
        patch_matches = 1
    elif patch_matches_raw is False:
        patch_matches = 0
    else:
        patch_matches = None

    canonical_available = 1 if patch_matches_raw is not None else 0

    validator_model = result.get("validator_model") or "claude-sonnet-4.5"

    conn.execute("DELETE FROM run_validations WHERE run_id = ?", (run_id,))

    conn.execute(
        """
        INSERT OR REPLACE INTO run_validations
            (validation_id, run_id, validated_at, validator_model,
             test_passed, infra_fail_detected, canonical_patch_available,
             patch_semantically_matches, verdict, confidence, justification)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            str(uuid.uuid4()),
            run_id,
            datetime.now(timezone.utc).isoformat(),
            validator_model,
            1 if result.get("test_passed", True) else 0,
            0,
            canonical_available,
            patch_matches,
            result.get("verdict", "FAIL"),
            result.get("confidence"),
            result.get("justification", ""),
        ),
    )
    conn.commit()


# ── Entry point ───────────────────────────────────────────────────────────────

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Persistence layer for APR batch validation verdicts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--db", required=True, metavar="PATH",
                        help="Path to the consolidated batch SQLite database.")
    parser.add_argument("--list-runs", action="store_true",
                        help="List runs needing validation (JSON output) instead of writing verdicts.")
    parser.add_argument("--force", action="store_true",
                        help="With --list-runs: include already-validated runs. "
                             "With write mode: allow overwriting existing verdicts.")
    parser.add_argument("--run-id", metavar="RUN_ID",
                        help="Filter to a single run_id.")
    return parser


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        print(json.dumps({"status": "error", "message": f"DB not found: {db_path}"}))
        sys.exit(1)

    conn = sqlite3.connect(db_path)

    # ── List mode ─────────────────────────────────────────────────────────────
    if args.list_runs:
        repo_root = _repo_root_from_db(db_path)
        runs = fetch_runs(conn, force=args.force, run_id=args.run_id, repo_root=repo_root)
        conn.close()
        print(json.dumps(runs))
        return

    # ── Write mode (stdin) ────────────────────────────────────────────────────
    try:
        raw = sys.stdin.read().strip()
        verdicts = json.loads(raw)
    except Exception as exc:
        conn.close()
        print(json.dumps({"status": "error", "message": f"Failed to parse stdin JSON: {exc}"}))
        sys.exit(1)

    if not isinstance(verdicts, list):
        conn.close()
        print(json.dumps({"status": "error", "message": "Expected a JSON array of verdicts on stdin."}))
        sys.exit(1)

    ok = errors = 0
    results_log: list[dict] = []

    for verdict in verdicts:
        run_id = verdict.get("run_id")
        if not run_id:
            errors += 1
            results_log.append({"error": "Missing run_id", "entry": verdict})
            continue
        try:
            write_validation(conn, run_id, verdict)
            results_log.append({
                "run_id": run_id,
                "verdict": verdict.get("verdict", "?"),
                "confidence": verdict.get("confidence"),
            })
            ok += 1
        except Exception as exc:  # noqa: BLE001
            errors += 1
            results_log.append({"run_id": run_id, "error": str(exc)})

    conn.close()
    print(json.dumps({
        "status": "ok" if errors == 0 else "partial",
        "written": ok,
        "errors": errors,
        "results": results_log,
    }))


if __name__ == "__main__":
    main()
