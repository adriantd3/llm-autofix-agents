from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from llm_autofix_agents.agent_flow import run_agent_baseline
from llm_autofix_agents.contracts import (
    RunInput,
    RunOutput,
    RunStatus,
    StopReason,
    TestResults,
    build_run_identity,
    load_container_instantiation_from_env,
)
from llm_autofix_agents.repo_source import PreparedRepository, prepare_target_repository
from llm_autofix_agents.runtime.docker_runner import ContainerRunRequest, DockerRunner, DockerRunnerError

_DEFAULT_AGENT_PROMPT = "Analyze a failing test and suggest a minimal fix strategy."


def app() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.command_name == "docker-smoke":
        raise SystemExit(_run_docker_smoke(args))
    if args.command_name == "contracts-smoke":
        raise SystemExit(_run_contracts_smoke(args))
    if args.command_name == "agent-smoke":
        raise SystemExit(_run_agent_smoke(args))
    if args.command_name == "runtime-contract-smoke":
        raise SystemExit(_run_runtime_contract_smoke(args))

    print("Welcome to LLM Autofix Agents!")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autofix")
    subcommands = parser.add_subparsers(dest="command_name")

    smoke_parser = subcommands.add_parser(
        "docker-smoke",
        help="Run a smoke command inside an ephemeral Docker container.",
    )
    smoke_parser.add_argument(
        "--repo",
        default=".",
        help="Path to the target repository that will be mounted inside the container.",
    )
    smoke_parser.add_argument(
        "--image",
        default="llm-autofix-runner:py313",
        help="Docker image used for the run.",
    )
    smoke_parser.add_argument(
        "--command",
        default="python --version",
        help="Command to execute inside the container.",
    )

    contracts_parser = subcommands.add_parser(
        "contracts-smoke",
        help="Validate baseline run contracts and print example payloads.",
    )
    contracts_parser.add_argument(
        "--prompt",
        default="Fix failing test in parser module",
        help="Prompt used to build the input model.",
    )

    agent_parser = subcommands.add_parser(
        "agent-smoke",
        help="Run a minimal baseline agent iteration with the configured LLM provider.",
    )
    agent_parser.add_argument(
        "--prompt",
        default=_DEFAULT_AGENT_PROMPT,
        help="Prompt passed to the baseline agent.",
    )

    subcommands.add_parser(
        "runtime-contract-smoke",
        help="Validate container runtime instantiation contract from RUN_* environment variables.",
    )
    return parser


def _run_docker_smoke(args: argparse.Namespace) -> int:
    try:
        request = ContainerRunRequest(
            repo_path=Path(args.repo),
            command=args.command,
            image=args.image,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    runner = DockerRunner()

    try:
        result = runner.run(request)
    except DockerRunnerError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(result.to_dict(), indent=2))
    return 0 if result.exit_code == 0 and not result.timed_out else 1


def _run_contracts_smoke(args: argparse.Namespace) -> int:
    run_input = RunInput(
        prompt=args.prompt,
        metadata={"source": "contracts-smoke"},
        target_repo=".",
        test_command="uv run pytest",
    )
    identity = build_run_identity(
        run_input=run_input,
        agent_config={"model": "baseline", "max_iterations": 3},
        iteration=1,
    )
    run_output = RunOutput(
        identity=identity,
        status=RunStatus.PARTIAL,
        stop_reason=StopReason.NO_PROGRESS,
        diff="",
        tests=TestResults(total=5, passed=3, failed=2),
        logs=["iteration=1", "agent step completed"],
        final_message="No progress detected after validation.",
    )
    payload = {
        "input": run_input.model_dump(mode="json"),
        "output": run_output.model_dump(mode="json"),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=True))
    return 0


def _run_agent_smoke(args: argparse.Namespace) -> int:
    prepared_repo: PreparedRepository | None = None
    prompt = args.prompt
    metadata: dict[str, str] = {"source": "agent-smoke"}
    target_repo = "."
    test_command = _resolve_optional_text(os.environ.get("RUN_TEST_COMMAND"))

    try:
        instantiation = load_container_instantiation_from_env()
    except ValueError:
        instantiation = None

    if instantiation is not None:
        if prompt == _DEFAULT_AGENT_PROMPT:
            prompt = instantiation.bootstrap_prompt
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
            print(str(exc), file=sys.stderr)
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


def _run_runtime_contract_smoke(args: argparse.Namespace) -> int:
    del args
    try:
        instantiation = load_container_instantiation_from_env()
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    print(json.dumps(instantiation.model_dump(mode="json"), indent=2, ensure_ascii=True))
    return 0


def _resolve_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


if __name__ == "__main__":
    app()
