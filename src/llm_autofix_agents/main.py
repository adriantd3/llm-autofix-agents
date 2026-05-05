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
    return parser


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
