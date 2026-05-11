# SPEC-011 Tasks

## Status: completed

## Tasks

- [x] Fase 0: Crear paquete `agents/instructions/`
  - [x] `instructions/__init__.py` (re-exports + new V2 symbols)
  - [x] `instructions/mono_agent.py`
  - [x] `instructions/handoff.py`
  - [x] `instructions/orchestrator.py` (3 new ORCHESTRATOR_V2_* constants)
  - [x] `instructions/planner_executor.py`
  - [x] Delete old `instructions.py`

- [x] Fase 1a: Nuevos perfiles de herramientas
  - [x] `APR_ORCHESTRATOR_EXPLORER_TOOLS` (alias for triage)
  - [x] `APR_ORCHESTRATOR_TEST_RUNNER_TOOLS`
  - [x] `APR_ORCHESTRATOR_MAIN_TOOLS`
  - [x] Register `explorer`, `test_runner`, `orchestrator_main` in `build_apr_tools()`

- [x] Fase 1b: Reescribir `architectures/orchestrator.py`
  - [x] 2 task-agents: `explorer` + `test_runner`
  - [x] Orchestrator main with direct write tools
  - [x] `as_tool()`: `explore_code`, `run_tests`
  - [x] Single shared model via `role="orchestrator"`

- [x] Fase 1c: Actualizar tests de arquitectura
  - [x] `test_orchestrator_architecture_wires_task_agents_and_tools`

- [x] Fase 2: Crear batch config
  - [x] `batches/bugsinpy-orchestrator-v2-multifile.yaml`

- [x] Fase 3: Crear spec 011
  - [x] `specs/011-orchestrator-task-agents/spec.md`
  - [x] `specs/011-orchestrator-task-agents/tasks.md`

- [x] Verificación: tests + lint
