# llm-autofix-agents

Automated program repair with LLM-based agents. Given a failing test, the system analyzes the failure, locates the bug, proposes a patch, applies it, and validates the fix. All happens autonomously inside Docker-sandboxed containers.

Built as an experimental platform to compare agent orchestration architectures and LLM models, measuring effectiveness, patch quality, token cost, and iteration convergence.

## How It Works

```
Bug (failing test) ──► Docker container
                          │
                          ▼
                 ┌─ Iteration loop ─┐
                 │  1. Agent explores │
                 │  2. Agent patches  │
                 │  3. Test validates │
                 │  4. Decide outcome│
                 └──────────────────┘
                          │
                          ▼
                  CORRECT / PLAUSIBLE / OVERFITTING / FAIL
```

Each bug runs in an ephemeral Docker container. The agent interacts with the codebase through a set of tools (read, search, edit, execute, git), and after the iteration loop a formal validation pipeline produces a verdict by comparing against the canonical fix and using an LLM-based semantic judge.

## Architectures

Four pluggable agent architectures, selected via batch config:

| Architecture | Description |
|---|---|
| `mono_agent` | Single agent handles the full repair cycle |
| `multi_agent_orchestrator` | Orchestrator delegates to read-only explorer + test runner sub-agents (`Agent.as_tool()`) |
| `planner_executor` | Planner investigates in iteration 1, executor applies and validates from iteration 2+ |
| `multi_agent_handoff` | Sequential handoff between triage, localizer, patcher, validator agents* |

*\*Discarded from formal evaluation — inoperable with local models.*

## Quick Start

```bash
# Install dependencies
uv sync

# (Optional) Configure API keys
cp .env.example .env

# Build Docker images
docker compose build runner
docker compose build bugsinpy-runner   # only for BugsInPy dataset
```

### Run a Batch

```bash
# Dry run — show the execution plan
make batch-dry-run BATCH_CONFIG=batches/quixbugs-mono-local-sample.yaml

# Execute
make batch BATCH_CONFIG=batches/quixbugs-mono-local-sample.yaml
```

Or directly:

```bash
uv run autofix batch batches/quixbugs-mono-local-sample.yaml
```

### Validate Results

```bash
uv run autofix validate --batch-dir results/<batch-dir>/ --create-views
```

### Other Commands

```bash
make format               # ruff format + lint
make test                 # run test suite
make docker-debug-shell   # shell into runner container
make aggregate OUT=analysis.db BATCH_DIRS="results/batch1 results/batch2"
```

## Batch Configuration

Batches are defined in YAML files under `batches/`:

```yaml
name: quixbugs-mono-local-sample
dataset: ../datasets/quixbugs.yaml

global:
  architecture: mono_agent
  llm:
    provider: ollama          # ollama | openai 
    model: gemma4:26b
    max_turns: 20
  max_iterations: 3
  timeout_seconds: 300

bugs:
  - gcd
  - flatten
  - mergesort
```

## Datasets

- **QuixBugs** — 40 Python bugs from the QuixBugs benchmark
- **BugsInPy** — Multi-project Python bug benchmark (requires `bugsinpy-runner` image)

Dataset configurations live in `datasets/`.

## LLM Providers

| Provider | Config key | Requirements |
|---|---|---|
| Ollama (local) | `ollama` | Ollama running on host, models pulled |
| OpenAI | `openai` | `OPENAI_API_KEY` in `.env` |
| Gemini | `gemini` | `GEMINI_API_KEY` in `.env` |
| OpenCode GO | `opencode-go` | `OPENCODE_GO_API_KEY` in `.env` |

## Validation Pipeline

Post-run validation produces a verdict for each fix:

- **CORRECT** — Patch matches the canonical fix semantically
- **PLAUSIBLE** — Fix passes the test but differs from the canonical solution
- **OVERFITTING** — Fix passes the test but modifies test files or is semantically wrong
- **FAIL** — Test still fails after the patch

Anti-overfitting measures: agents are explicitly instructed not to modify test files, and the validation pipeline detects test-file tampering and regression.

## Observability

Every run produces structured data in the results directory:

- **SQLite** — Per-run `run.db`, mergeable into batch-level `batch.db`
- **JSONL events** — Full tool call and agent event trace
- **Live Markdown** — Human-readable iteration log (`live.md`)
- **Patches** — Per-iteration unified diffs

## Project Structure

```
src/llm_autofix_agents/
├── agents/instructions/    # Per-architecture prompt modules
├── architectures/          # Factory + architecture builders
├── flow/                   # Core orchestration loop & policies
├── tools/                  # APR toolkit (11 tool functions)
├── llm/                    # Provider, settings, agent factory
├── batch/                  # Batch execution (Docker orchestration)
├── datasets/               # Dataset adapters (QuixBugs, BugsInPy)
├── validation/             # Post-run LLM judge for fix quality
├── observability/          # SQLite, JSONL, Markdown event emission
└── main.py                 # CLI entrypoint
```

## Tech Stack

- **Python 3.13** with `uv` for dependency management
- **OpenAI Agents SDK** (v0.14+) — agent execution, handoffs, tool calling
- **Pydantic** — data contracts and validation
- **Docker / Docker Compose** — sandboxed execution containers
- **SQLite + JSONL** — structured observability

## License

This project is part of a Master's thesis (TFM) at Universidad de Málaga