from __future__ import annotations

import argparse
import json
import logging
import os
import sys

from llm_autofix_agents.agent_flow import run_agent_baseline
from llm_autofix_agents.contracts import ContainerInstantiation, RunInput, RunStatus
from llm_autofix_agents.repo_source import PreparedRepository, prepare_target_repository

_DEFAULT_AGENT_PROMPT = "Analyze a failing test and suggest a minimal fix strategy."

logger = logging.getLogger(__name__)


def app() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command_name == "run":
        raise SystemExit(_run_run(args))

    parser.print_help()


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autofix")
    subcommands = parser.add_subparsers(dest="command_name")
    subcommands.add_parser("run", help="Run the Docker Compose entrypoint.")
    return parser


def _run_run(args: argparse.Namespace) -> int:
    del args
    _configure_logging()
    prepared_repo: PreparedRepository | None = None
    metadata: dict[str, object] = {"source": "run"}
    target_repo = "."
    prompt = os.environ.get("RUN_BOOTSTRAP_PROMPT", _DEFAULT_AGENT_PROMPT).strip() or _DEFAULT_AGENT_PROMPT
    test_command = _resolve_optional_text(os.environ.get("RUN_TEST_COMMAND"))

    try:
        instantiation = ContainerInstantiation.from_env()
    except ValueError:
        instantiation = None

    if instantiation is not None:
        prompt = instantiation.bootstrap_prompt or prompt
        metadata.update(
            {
                "runtime_repository": instantiation.repository,
                "runtime_branch": instantiation.branch,
                "runtime_architecture": instantiation.architecture,
            }
        )
        try:
            prepared_repo = prepare_target_repository(
                repository=instantiation.repository,
                branch=instantiation.branch,
            )
        except ValueError as exc:
            logger.error("%s", exc)
            return 2
        target_repo = str(prepared_repo.path)

    run_input = RunInput(
        prompt=prompt,
        metadata=metadata,
        target_repo=target_repo,
        test_command=test_command,
    )
    try:
        run_output = run_agent_baseline(run_input)
    finally:
        if prepared_repo is not None:
            prepared_repo.cleanup()

    payload = {
        "input": run_input.model_dump(mode="json"),
        "output": run_output.model_dump(mode="json"),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0 if run_output.status == RunStatus.SUCCESS else 1


def _configure_logging() -> None:
    level_name = os.environ.get("AUTOFIX_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(level=level, format="%(message)s", stream=sys.stderr, force=True)


def _resolve_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


if __name__ == "__main__":
    app()
