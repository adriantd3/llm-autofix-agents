# Dataset Execution Architecture

## Overview

The batch execution system uses a **dataset adapter pattern** to keep agents and runtime logic dataset-agnostic. Different APR datasets (QuixBugs, BugsInPy, SWE-bench Lite) are executed through one normalized case contract.

Every adapter produces a `PreparedExecutionCase` with both host and container workspace paths. This avoids mixing remote repos, host-only paths, and container-only paths, and prevents one bug run from mutating another bug run's workspace.

## Architecture

### Sandbox model: one container per bug

The agent **never** runs on the host. For each bug, the host:

1. Prepares a workspace under `./benchmark-workspaces/<batch_id>/<case_id>/`
2. Captures the failing test output from the host workspace
3. Spins up a **fresh Docker container** via `docker compose run --rm`
4. The container mounts the workspace at `/benchmark-workspaces/<batch_id>/<case_id>/`
5. Inside the container, `autofix run` operates on the mounted workspace (git branches, file edits, tests)
6. The container exits and is removed (`--rm`)
7. The host parses the result and cleans up the workspace

```
autofix batch <batch.yml>
  -> load BatchConfig
  -> load DatasetConfig
  -> adapter = DatasetAdapterRegistry.get(dataset.type)
  -> expand selected bugs
  -> for each bug:
       case = adapter.prepare_case(context, bug)
       error_output = capture_error_output(case.host_workspace, case.test_command)
       prompt = PromptBuilder.build(template, case.prompt_variables, error_output)
       env = RuntimeEnvBuilder.build(case, config, prompt)
       docker compose run --rm runner   <- fresh container per bug
       parse result
       cleanup workspace
  -> write BatchSummary
```

No `if dataset.type == ...` logic exists in `BatchRunner`. All dataset-specific behavior lives in adapters.

## Key Concepts

### PreparedExecutionCase

Every adapter must produce a frozen dataclass with:

- `case_id`: unique identifier for this bug case
- `dataset_name` / `dataset_type`: for tracking and reporting
- `host_workspace`: path used by the host-side batch runner for preparation and error capture
- `container_workspace`: equivalent mounted path inside Docker (`/benchmark-workspaces/<batch_id>/<case_id>`)
- `test_command`: the command to run for error capture and validation
- `prompt_variables`: dict of variables injected into the prompt template
- `metadata`: optional dataset-specific metadata
- `cleanup_paths`: paths to clean up after the run

This replaces direct use of `DatasetConfig.repository`, `DatasetConfig.branch`, and `DatasetConfig.resolve_test_command()` inside `BatchRunner`.

### DatasetAdapter (Protocol)

Each adapter implements:

```python
class DatasetAdapter(Protocol):
    type: str

    def prepare_case(
        self,
        context: DatasetPreparationContext,
        bug: BugEntry,
    ) -> PreparedExecutionCase:
        ...
```

### DatasetAdapterRegistry

Maps dataset type strings to adapter instances:

- `"quixbugs"` -> `QuixBugsAdapter`
- `"bugsinpy"` -> `BugsInPyAdapter`

Adding a new dataset requires only a new adapter and a YAML config. No changes to agents or runtime architecture are needed.

## Dataset-Specific Behavior

### QuixBugsAdapter

- Requires `dataset.repository.url` and `dataset.repository.branch`
- Creates one host workspace per case via shallow clone
- Resolves `test_command` from `bug.test_command` or `dataset.test.command_template`
- Prompt variables: `bug_id`, `program`, `test`, `test_command`, `dataset_name`

### BugsInPyAdapter

- Reads from `bug.metadata`: `project`, `bug_id`, `version` (defaults to `"0"`)
- Executes configurable `checkout_command_template` from `dataset.tooling`
- Optionally executes `compile_command` in the workspace
- Resolves test command from `bug.test_command`, `dataset.tooling.test_command`, or defaults to `bugsinpy-test`

### SWE-bench Lite (Future)

Will be implemented as another adapter. No runtime architecture changes required.

## Local Mounted Workspaces

`RUN_REPOSITORY` can now point to a local mounted workspace path (inside the Docker container at `/benchmark-workspaces/...`). The runner passes an empty `RUN_BRANCH` for local workspaces. The `prepare_target_repository` function detects local directories and returns them directly without cloning.

## Batch Config Schema

### DatasetConfig

```yaml
type: quixbugs
name: quixbugs-python
language: python
repository:
  url: https://github.com/jkoppel/QuixBugs.git
  branch: master
test:
  command_template: "uv run --with pytest pytest python_testcases/test_{bug_id}.py"
bugs:
  - id: gcd
    program: gcd
    test: python_testcases/test_gcd.py
```

### BugsInPy DatasetConfig

```yaml
type: bugsinpy
name: bugsinpy
language: python
tooling:
  checkout_command_template: "bugsinpy-checkout -p {project} -i {bug_id} -v {version} -w {host_workspace}"
  compile_command: "bugsinpy-compile"
  test_command: "bugsinpy-test"
bugs:
  - id: youtube-dl-2
    program: youtube-dl
    metadata:
      project: youtube-dl
      bug_id: "2"
      version: "0"
```

## Error Handling

A preparation failure in one case produces a `BugRunResult(status="infra_failure")` for that case and continues the batch. It does not kill the whole batch unless Docker build fails.

## Workspace Layout

```
<project_dir>/benchmark-workspaces/<batch_id>/<case_id>
```

The corresponding container path is:

```
/benchmark-workspaces/<batch_id>/<case_id>
```

Both are created and cleaned up per-case by the adapter.