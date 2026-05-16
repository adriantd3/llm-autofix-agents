from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from llm_autofix_agents.batch.runner import BatchRunner

_DEFAULT_AGENT_PROMPT = "Analyze a failing test and suggest a minimal fix strategy."

logger = logging.getLogger(__name__)


def app() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command_name == "batch":
        exit_code = _run_batch(args)
        _hard_exit(exit_code)

    if args.command_name == "validate":
        exit_code = _run_validate(args)
        _hard_exit(exit_code)

    parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autofix")
    subcommands = parser.add_subparsers(dest="command_name")

    batch_parser = subcommands.add_parser("batch", help="Run a batch of bugs from a config file.")
    batch_parser.add_argument("config", type=Path, help="Path to the batch YAML config file.")
    batch_parser.add_argument(
        "--compose-file",
        type=Path,
        default=Path("docker-compose.yml"),
        help="Path to docker-compose.yml (default: docker-compose.yml)",
    )
    batch_parser.add_argument(
        "--project-dir",
        type=Path,
        default=None,
        help="Path to the project directory (default: current directory)",
    )
    batch_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show the batch plan without executing runs.",
    )

    validate_parser = subcommands.add_parser(
        "validate",
        help="Post-run: validate fixes in a batch DB using an LLM judge.",
    )
    validate_db = validate_parser.add_mutually_exclusive_group(required=True)
    validate_db.add_argument("--db", type=Path, help="Path to a run.db or batch.db file.")
    validate_db.add_argument(
        "--batch-dir",
        type=Path,
        help="Path to a batch result directory (uses batch.db inside it).",
    )
    validate_parser.add_argument(
        "--run-id",
        default=None,
        help="Validate only this specific run_id (default: all runs in the DB).",
    )
    validate_parser.add_argument(
        "--canonical-root",
        type=Path,
        default=None,
        help=(
            "Base directory for canonical (ground-truth) patches. "
            "QuixBugs: path to the cloned repo. BugsInPy: parent dir of {problem_id}/bug_patch.txt."
        ),
    )
    validate_parser.add_argument(
        "--provider",
        default=os.environ.get("LLM_PROVIDER", "openai"),
        help="LLM provider for the validator (default: $LLM_PROVIDER or 'openai').",
    )
    validate_parser.add_argument(
        "--model",
        default=os.environ.get("LLM_MODEL", "gpt-4.1-mini"),
        help="Model name for the validator (default: $LLM_MODEL or 'gpt-4.1-mini').",
    )
    validate_parser.add_argument(
        "--force",
        action="store_true",
        help="Re-validate runs that already have a verdict.",
    )
    validate_parser.add_argument(
        "--create-views",
        action="store_true",
        help="Create analysis views (v_run_summary, v_architecture_metrics, v_bug_heatmap) after validation.",
    )

    return parser


def _run_validate(args: argparse.Namespace) -> int:
    _configure_logging()
    from llm_autofix_agents.llm.settings import LLMSettings, ProviderType
    from llm_autofix_agents.observability.sqlite_store import SQLiteObservabilityStore
    from llm_autofix_agents.validation.runner import ValidationRunner

    # Resolve the DB path.
    if args.db:
        db_path = args.db.resolve()
    else:
        db_path = args.batch_dir.resolve() / "batch.db"

    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}", file=sys.stderr)
        return 1

    # Build LLM settings for the validator.
    llm_settings = LLMSettings(
        provider=ProviderType(args.provider),
        model=args.model,
    )

    runner = ValidationRunner(
        db_path=db_path,
        llm_settings=llm_settings,
        canonical_root=args.canonical_root,
        force_revalidate=args.force,
    )

    if args.run_id:
        results = [runner.validate_run(args.run_id)]
    else:
        results = runner.validate_all()

    if args.create_views:
        store = SQLiteObservabilityStore(db_path=db_path)
        store.create_analysis_views()
        logger.info("Analysis views created in %s", db_path)

    # Print summary table.
    print(f"\n{'run_id':<55} {'verdict':<12} {'conf':>5}  justification")
    print("-" * 110)
    for r in results:
        if r.skipped:
            print(f"{r.run_id:<55} {'SKIPPED':<12}  ({r.skip_reason})")
        else:
            conf = f"{r.confidence:.2f}" if r.confidence is not None else "  n/a"
            short_just = (r.justification or "")[:60].replace("\n", " ")
            print(f"{r.run_id:<55} {r.verdict:<12} {conf:>5}  {short_just}")

    total = len(results)
    validated = sum(1 for r in results if not r.skipped)
    correct = sum(1 for r in results if r.verdict == "CORRECT")
    plausible = sum(1 for r in results if r.verdict in ("CORRECT", "PLAUSIBLE"))
    print(f"\nTotal: {total}  Validated: {validated}  CORRECT: {correct}  PLAUSIBLE: {plausible}")
    return 0


def _run_batch(args: argparse.Namespace) -> int:
    _configure_logging()
    config_path = args.config.resolve()
    project_dir = args.project_dir.resolve() if args.project_dir else Path.cwd()
    compose_file = args.compose_file
    if not compose_file.is_absolute():
        compose_file = project_dir / compose_file

    runner = BatchRunner(
        compose_file=compose_file,
        project_dir=project_dir,
    )
    summary = runner.run_batch(config_path, dry_run=args.dry_run)
    print(summary.model_dump_json(indent=2, ensure_ascii=True))
    return 0


def _configure_logging() -> None:
    level_name = os.environ.get("AUTOFIX_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr, force=True)


def _hard_exit(exit_code: int) -> None:
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(exit_code)


if __name__ == "__main__":
    app()
