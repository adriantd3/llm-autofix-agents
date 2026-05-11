# SPEC-011: Orchestrator Task-Agent Architecture + Instructions Package Refactor

## Context

The `multi_agent_orchestrator` architecture was a state machine, not a real orchestrator.
It hardcoded the sequence `localize_bug → apply_fix → validate_patch` in the manager prompt
and delegated all tool access to 3 role-based sub-agents, preventing the manager from acting
autonomously based on evidence.

`agents/instructions.py` had grown to ~560 lines with 11 constants for 4 architectures — unsustainable.

## Goals

1. Rewrite the `multi_agent_orchestrator` architecture with 2 functional capability task-agents.
2. Refactor `agents/instructions.py` into a proper package `agents/instructions/`.
3. Add a validation batch config for 3 cross-file BugsInPy bugs.

## Design

### Instructions Package (`agents/instructions/`)

One module per architecture, replacing the single flat file:
- `mono_agent.py` — `MONO_AGENT_APR_INSTRUCTIONS`
- `handoff.py` — `HANDOFF_TRIAGE/LOCALIZER/PATCHER/VALIDATOR_INSTRUCTIONS`
- `orchestrator.py` — `ORCHESTRATOR_V2_MAIN/EXPLORER/TEST_RUNNER_INSTRUCTIONS` (new)
- `planner_executor.py` — `PLANNER_INSTRUCTIONS`, `EXECUTOR_INSTRUCTIONS`
- `__init__.py` — re-exports all (backwards-compatible import path)

The 4 old `ORCHESTRATOR_*` constants are **not migrated** (replaced by 3 new V2 constants).

### Orchestrator v2 Architecture

**Task-agents** (capability-based, not role-based):

| Agent | Profile | Role |
|-------|---------|------|
| `explorer` | `explorer` (= triage) | Read-only: examines files, returns compact summary |
| `test_runner` | `test_runner` | Runs tests, returns structured verdict |

**Orchestrator main** uses `orchestrator_main` profile (full write tools, no `run_test_target`).
It calls `explore_code` and `run_tests` as `Agent.as_tool()` delegates, and applies fixes **directly**.

All 3 agents share the same model (no per-role model overrides).

### New Tool Profiles

| Profile | Tools |
|---------|-------|
| `explorer` | alias for `triage` (read-only) |
| `test_runner` | `execute_command`, `run_test_target`, `read_file` |
| `orchestrator_main` | full write except `run_test_target` and `apply_unified_diff` |

## Key Architectural Decisions

- **No `verifier/critic`** in this spec (future ablation study).
- **No handoffs** — orchestrator stays in control throughout.
- **Autonomous ordering** — orchestrator decides when/how many times to call each task-agent.
- Architecture enum name stays `multi_agent_orchestrator` (no migration needed).

## Docker Container Architecture (BugsInPy)

BugsInPy requires a dual-container strategy because the agent runtime and the
bug test environments need different (incompatible) Python versions.

### The Portability Constraint

`bugsinpy-compile` creates a Python venv with `python3 -m venv env`. The venv
contains **absolute symlinks** to the Python interpreter at build time:

```
env/bin/python3  →  /usr/local/bin/python3   (resolves at runtime in the container)
env/bin/pytest   →  shebang: #!/usr/local/bin/python3
```

These symlinks resolve to whatever `python3` is in the container that **runs
the tests**. Therefore, venv creation and test execution must happen in the
**same container**. A venv created in a Python 3.8 container cannot be used
in a Python 3.13 container — the symlinks would resolve to the wrong interpreter
and break all imports (e.g. `ModuleNotFoundError: No module named 'pipes'`).

### Dual-Python Strategy in `bugsinpy-runner`

Both preparation and agent execution use `bugsinpy-runner`:

```
bugsinpy-runner (python:3.8-slim)
├── system python3 = 3.8
│   └── bugsinpy-compile creates env/ → symlinks resolve to Python 3.8 ✓
│       test execution: . env/bin/activate && bash bugsinpy_run_test.sh ✓
└── uv (UV_PYTHON_INSTALL_DIR=/opt/uv-python, world-readable)
    └── downloads Python 3.13 for our agent (pyproject.toml requires >=3.13)
        .venv/bin/python3 → /opt/uv-python/cpython-3.13/bin/python3 ✓
```

`UV_SYSTEM_PYTHON` is NOT set, so uv does not use system Python 3.8 for the
project venv. The two Python environments are fully isolated.

### Why Not Split Containers?

Splitting prep (`bugsinpy-runner`) and agent+tests (`runner`) fails because:
- `runner` has Python 3.13 at `/usr/local/bin/python3`
- Bug venv symlinks resolve to Python 3.13 in `runner`
- Old BugsInPy projects use modules removed in 3.12-3.13 (`pipes`, `imp`)
- Tests fail before any assertion runs — not a model quality issue

### Container Responsibilities

| Container | Purpose | Python |
|-----------|---------|--------|
| `bugsinpy-runner` | checkout + compile + **agent + tests** | 3.8 (system) + 3.13 (uv) |
| `runner` | agent + tests for non-BugsInPy datasets | 3.13 (system, UV_SYSTEM_PYTHON=1) |

## Files Changed

- `src/llm_autofix_agents/agents/instructions/` (new package, replaces `instructions.py`)
- `src/llm_autofix_agents/agents/instructions.py` (deleted)
- `src/llm_autofix_agents/tools/profiles.py` (new profiles)
- `src/llm_autofix_agents/architectures/orchestrator.py` (full rewrite)
- `tests/test_architectures.py` (updated orchestrator test)
- `batches/bugsinpy-orchestrator-v2-multifile.yaml` (new)
- `docker/bugsinpy.Dockerfile` (dual-Python: 3.8 base + uv-managed 3.13)
- `src/llm_autofix_agents/datasets/bugsinpy.py` (runner_service = bugsinpy-runner)
