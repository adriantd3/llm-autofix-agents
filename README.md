# llm-autofix-agents

> Experimental automated program repair (APR) platform using LLM agents.

## What it is

A system that takes a program with a failing test, launches an LLM agent on the code, applies changes, and verifies the fix. Used as an experimental platform to compare agent architectures and models on real-world bug datasets.

## How to run

Requirements: `uv`, `docker`, `make`.

```bash
uv sync
```

Run a batch of bugs from a YAML config:

```bash
uv run autofix batch batches/quixbugs-mono-local-sample.yaml
```

Simulate without executing:

```bash
uv run autofix batch batches/quixbugs-mono-local-sample.yaml --dry-run
```

Useful commands:

```bash
make format   # format code
make test     # run tests
```

Minimum environment config (`.env` file):

```bash
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11500/v1
LLM_MODEL=llama3.1:8b
```

OpenAI and Gemini are also supported.

## How it works

The host only orchestrates; all dataset-specific commands and agent execution happen inside Docker containers.

Simplified flow:

1. `BatchRunner` reads a YAML config with the list of bugs.
2. For each bug, a `DatasetAdapter` prepares an isolated workspace under `./benchmark-workspaces/`.
3. The failing test is run **inside** the container to capture the error output.
4. `docker compose run --rm <service>` is launched with the prompt and agent configuration.
5. The APR agent inside the container inspects the code, applies changes, and verifies the fix.

### Architectures

- **mono_agent**: a single agent that analyzes, localizes, patches, and validates.
- **multi_agent_handoff**: a team of specialized agents (triage, localizer, patcher, validator) that hand off control.

### Containers

- **runner**: generic service for datasets without special dependencies (QuixBugs).
- **bugsinpy-runner**: service with `bugsinpy-*` tools installed (BugsInPy).

## Datasets

Datasets are defined in YAML under `datasets/` and referenced from batch configs in `batches/`.

- **QuixBugs**: 40 Python bugs. Each bug is cloned from the official repo into an isolated workspace.
- **BugsInPy**: real-world bugs from Python projects. Requires `bugsinpy-runner` for checkout and compilation.
