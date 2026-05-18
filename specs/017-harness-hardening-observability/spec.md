# SPEC-017: Harness Hardening & Observability — BugsInPy Python 3.8 + infra_failure Diagnosis

## Metadata
- Date: 2026-05-17
- Branch: chore/012/telemetry-observability-refactor
- Trigger batch: `batch-bugsinpy-architecture-check-20260517T174024Z` (12/12 infra_failure)

---

## Context

The first full BugsInPy batch (`bugsinpy-architecture-check-20260517T174024Z`) revealed two
classes of silent infrastructure failure that together blocked all 12 bugs:

**A — Wrong Python interpreter (5 bugs):** matplotlib-1, pysnooper-1, luigi-1, spacy-1, keras-1
ran their tests under uv's Python 3.14 (`/opt/uv-python/cpython-3.14.5-linux-x86_64-gnu/`)
instead of the per-bug venv's Python 3.8. Errors like `ModuleNotFoundError: No module named
'distutils'` (removed in 3.12) were misread as real bugs. Root cause: the test command used
`. env/bin/activate && ...`, which silently failed for venvs where `activate` was absent or
broken, causing subsequent commands to inherit the `uv run` PATH with Python 3.14.

**B — Exception details invisible (2 bugs):** black-6 and scrapy-33 failed with
`stop_reason: infra_failure` before any agent ran. The exception message was captured in
`output_builder.exception_failure` as `str(exc)` and stored only in `RunOutput.artifacts["errors"]`
— an in-memory structure never written to SQLite or JSONL. Diagnosis required manual log tracing.

Additionally, batch analysis revealed several harness bugs that wasted agent turns without
contributing to bug resolution.

---

## Part A — BugsInPy Python 3.8 Venv Hardening

### A1 — Compile validation: `env/bin/activate` instead of `env`

**File**: `src/llm_autofix_agents/datasets/bugsinpy.py`

**Problem**: `_COMPILE_REQUIRED_FILES` checked only that the `env/` directory existed.
A compiled but broken venv passes this check.

**First attempt** (A1a): checked `env/bin/python`. This regressed: `env/bin/python` is a
symlink chain (`python → python3 → /usr/local/bin/python3`) pointing to a Docker-absolute path.
`Path.exists()` follows symlinks and returns False on the host — all 12 bugs became `infra_failure`.

**Final fix** (A1b): check `env/bin/activate` instead. The activate script is a regular shell
file (not a symlink), so `Path.exists()` reliably returns True on the host when the venv was
correctly compiled by `bugsinpy-compile`.

```python
_COMPILE_REQUIRED_FILES = (
    "bugsinpy_compile_flag",
    "env/bin/activate",  # regular file; env/bin/python is a broken symlink on the host
)
```

### A2 — Test command: direct venv invocation without activate

**File**: `src/llm_autofix_agents/datasets/bugsinpy.py` → `_resolve_test_command`

**Old command** (fragile):
```bash
. env/bin/activate && (pip install -e . --no-deps -q 2>/dev/null || true) && bash bugsinpy_run_test.sh
```
If `activate` failed silently, `pip` and `pytest` resolved to uv's Python 3.14.

**New command**:
```bash
test -x env/bin/python && test -f bugsinpy_run_test.sh && test -f bugsinpy_compile_flag || exit 2;
env/bin/pip install -e . --no-deps -q 2>/dev/null || true;
(env/bin/python -m pytest --version >/dev/null 2>&1 || env/bin/pip install pytest -q 2>/dev/null || true);
PATH="$(pwd)/env/bin:$PATH" VIRTUAL_ENV="$(pwd)/env" bash bugsinpy_run_test.sh
```

Rationale for each change:
- `test -x env/bin/python` fails fast with exit 2 if the Python binary is absent (inside Docker
  this path works; the check is for early detection of broken compilation).
- `env/bin/pip install -e .` registers the project in the venv without depending on `activate`.
- Pytest availability guard: `env/bin/pytest` may be absent from some compiled venvs
  (confirmed for luigi-1). If `env/bin/python -m pytest` fails, install pytest via `env/bin/pip`
  to ensure `env/bin/pytest` exists and uses Python 3.8 before the test script runs.
- `PATH="$(pwd)/env/bin:$PATH"` prepends the venv; `bash bugsinpy_run_test.sh` then resolves
  `pytest` to `env/bin/pytest` (Python 3.8) rather than the system uv-managed Python 3.14.

**Known limitation**: `env/bin/pip install pytest` installs the latest compatible version, which
may differ from the version pinned by `bugsinpy-compile`. This is acceptable: the test command
runs inside the Docker container with an isolated venv; version drift only matters if a specific
pytest behavior is under test (none of the tracked bugs require this).

---

## Part B — infra_failure Exception Observability

### B1 — Traceback capture in orchestrator

**File**: `src/llm_autofix_agents/flow/orchestrator.py`

Added `import traceback as _traceback`. The bare `except Exception as exc` block now passes:
```python
message=f"{type(exc).__name__}: {exc}",
details={"exception_type": type(exc).__name__, "traceback": _traceback.format_exc()}
```
to `output_builder.exception_failure`.

### B2 — `exception_failure` accepts `details`

**File**: `src/llm_autofix_agents/flow/lifecycle/output_builder.py`

Added optional `details: dict[str, Any] | None = None` parameter to `exception_failure`.
Passed through to `RunError(details=details or {})`. The `RunError` dataclass already had a
`details` field; no contract change required.

### B3 — `RunErrored` event + schema migration

**Files**: `observability/events.py`, `sqlite_schema.py`, `sqlite_store.py`

New dataclass `RunErrored` added to `ObservabilityEvent` union:
```python
@dataclass(frozen=True)
class RunErrored:
    run_id: str
    error_type: str
    error_message: str
    error_category: str
    traceback: str | None
    occurred_at: str
    event_type: Literal["run_errored"] = field(default="run_errored", init=False)
```

`SCHEMA_VERSION` bumped 7 → 8. Four nullable columns added to `runs`:
`error_type TEXT NULL`, `error_message TEXT NULL`, `error_category TEXT NULL`,
`error_traceback TEXT NULL`.

`MIGRATION_V7_TO_V8` adds these columns via `ALTER TABLE`. `initialize()` applies it when
upgrading an existing v7 database (no data loss for prior runs; new columns are NULL).

`update_run_error` method added to `RunStore` for the `UPDATE runs SET ... WHERE run_id=?`.

### B4 — Emitter, observers, finalizer

**File**: `observability/emitter.py` — `record_run_error(*, error_type, error_message, error_category, traceback)` method dispatches a `RunErrored` event using `self._run_id` (consistent with all other `Emitter` methods).

**File**: `observability/jsonl_observer.py` — `case RunErrored():` writes `event="run_errored"` to `events.jsonl`.

**File**: `observability/observer.py` — `case RunErrored():` calls `self._store.update_run_error(...)`.

**File**: `flow/lifecycle/finalizer.py` — `_emit_run_errors()` drains `output.artifacts["errors"]` and calls `emitter.record_run_error(...)` for each error before `_emit_run_finished`. This covers all three paths that produce errors via `output_builder`: `exception_failure`, `validation_failure`, `branch_cleanup_failed`.

---

## Part C — Context Engineering Parity (Cross-Architecture)

Batch analysis of all architectures (SPEC-015 and post-run reviews) identified two environment
rules that were present in `orchestrator.py` but missing from `mono_agent.py` and
`planner_executor.py`.

### C1 — `WINDOWED_READ_RULE`

**Added to `_shared.py`** and imported into all three architecture instruction files.

Rule: always specify `start_line`/`end_line` in `read_file`, target 40–80 line windows, use
`line_count` to paginate. Prevents agents from attempting to read entire large source files in
one call (which truncates silently and makes the agent re-read the same range repeatedly).

### C2 — `VENV_ENV_DIR_RULE`

**Added to `_shared.py`** and imported into all three architecture instruction files.

Rule: never recreate `env/` with `python -m venv env`. Use `env/bin/pip` to install missing
packages. Do not list, read, or search files inside `env/`.

**Corrected framing vs. initial draft**: the first version said the venv was "read-only".
It is not — `env/bin/pip install` by the agent is explicitly supported and confirmed working
(pysnooper-1 succeeded by running `env/bin/pip install python_toolbox`). The rule
warns against *recreating* the venv (which destroys the compiled 3.8 environment) and against
using the system `pip` (which installs to Python 3.14's site-packages, invisible to the test runner).

---

## Part D — Bug Fixes Discovered During Batch Analysis

### D1 — `git_status_summary` counted untracked files as agent edits

**File**: `src/llm_autofix_agents/tools/git_tools.py`

**Problem**: `git status --short --branch` includes `??` lines for untracked files. The tool
counted all status lines (after the branch line) as `changed_files`. BugsInPy workspaces have
~10 untracked metadata files (`bugsinpy_run_test.sh`, `bugsinpy_compile_flag`, `env/`, etc.)
committed in the benchmark container but untracked in the sparse git checkout. black-6 showed
`changed_files: 10` at run start — the agent spent all 21 turns investigating phantom changes,
never made an edit, and reached `max_turns`.

**Fix**: filter `??`-prefixed lines from the `changes` list:
```python
changes = [line for line in lines[1:] if not line.startswith("??")]
```

### D2 — `_resolve_path_under_root` crash on stdlib paths

**File**: `src/llm_autofix_agents/flow/policies/iteration.py`

**Problem**: The heuristic loop in `_resolve_path_under_root` builds `Path(*parts[i:])` and
tries `repo_root / suffix`. When `parts[0]` is empty (absolute paths like
`/opt/uv-python/.../importlib/__init__.py`), `Path(*parts[0:])` produces an absolute path.
In Python, `Path('/repo') / Path('/abs')` discards `/repo` and returns `/abs` — the function
returned the stdlib path instead of None, causing `_format_source_function` to read unrelated
stdlib code and crash with `ValueError: '...unittest/mock.py' is not in the subpath`.

**Fix**: skip heuristic suffixes that are absolute:
```python
for i in range(len(parts)):
    suffix = Path(*parts[i:])
    if suffix.is_absolute():
        continue  # Path('/') + absolute discards repo_root; skip
    possible = repo_root / suffix
    if possible.exists():
        return possible
```
Additional guard in `_extract_source_function_under_test`: verify `candidate.relative_to(repo_root)`
succeeds before using the path.

### D3 — Test file guard missed `tests_*.py` filenames

**Files**: `flow/policies/validation.py` (`_is_test_file`), `tools/edit_tools.py` (`_is_test_file_path`)

**Problem**: the guards caught `test_*.py` (singular) but not `tests_*.py` (plural). The tqdm
project has `tqdm/tests/tests_contrib.py` — a test file named `tests_contrib.py` whose stem
`tests_contrib` starts with `tests_` (not `test_`). The agent modified it and the run was
accepted as valid (false positive success).

**Fix**: added `stem.startswith("tests_")` check to both functions. Both now also catch any
directory component named `test` or `tests` (not just path prefixes). The two functions were
already in sync on the singular case; now both handle the plural as well.

---

## Batch Results

| Batch | Bugs | Infra OK | Resolved | Notes |
|-------|------|----------|----------|-------|
| `20260517T174024Z` | 12 | 7 | — | Pre-fix baseline; Python 3.14 errors visible |
| `20260517T193216Z` | 12 | 0 | — | Regression: `env/bin/python` symlink broken on host |
| `20260517T202438Z` | 12 | ~10 | see below | After A1b fix (activate check) |

In `20260517T202438Z` with 1 iteration / 20 turns:
- **thefuck-1, ansible-5, tornado-9, tqdm-1, sanic-1**: infrastructure OK, tests ran under Python 3.8
- **black-6**: infra OK post-D1 fix; agent no longer saw phantom changed_files. Root cause of black's bug is a valid repair target.
- **luigi-1**: still exit_code=4 (collection error) because `env/bin/pytest` was missing. Fixed in D-pytest-guard (A2 update).
- **keras-1, spacy-1, matplotlib-1**: Python 3.8 venv issues specific to model weights / C extensions — not resoluble via text editing. Classified as out-of-scope for APR.
- **black-6, scrapy-33**: `infra_failure` before agent started. Post-B changes now surface exception type and traceback in `events.jsonl` and SQLite for diagnosis.

---

## Files Changed

| File | Change |
|------|--------|
| `datasets/bugsinpy.py` | A1: `_COMPILE_REQUIRED_FILES` uses `env/bin/activate`; A2: new test command |
| `flow/orchestrator.py` | B1: traceback capture in exception handler |
| `flow/lifecycle/output_builder.py` | B2: `details` param in `exception_failure` |
| `observability/events.py` | B3: `RunErrored` dataclass + union entry |
| `observability/sqlite_schema.py` | B3: schema v8, 4 error columns, migration |
| `observability/sqlite_store.py` | B3: `update_run_error`, migration v7→v8 |
| `observability/emitter.py` | B4: `record_run_error` method |
| `observability/jsonl_observer.py` | B4: `case RunErrored()` handler |
| `observability/observer.py` | B4: `case RunErrored()` → SQLite |
| `flow/lifecycle/finalizer.py` | B4: `_emit_run_errors` before `_emit_run_finished` |
| `agents/instructions/_shared.py` | C1+C2: `WINDOWED_READ_RULE`, `VENV_ENV_DIR_RULE` |
| `agents/instructions/mono_agent.py` | C1+C2: import + embed both rules |
| `agents/instructions/orchestrator.py` | C2: import + embed `VENV_ENV_DIR_RULE` |
| `agents/instructions/planner_executor.py` | C1+C2: import + embed both rules |
| `tools/git_tools.py` | D1: filter `??` untracked from `changed_files` |
| `flow/policies/iteration.py` | D2: `_resolve_path_under_root` absolute-path guard |
| `flow/policies/validation.py` | D3: `_is_test_file` catches `tests_*.py` |
| `tools/edit_tools.py` | D3: `_is_test_file_path` catches `tests_*.py` |
| `tests/test_batch.py` | Update fixtures for new compile artifact paths |
| `tests/unit/.../test_validation_schema.py` | Expect schema v8 |

---

## Regression Check

`pytest tests/ -q` — 322 passed, 0 new failures.
