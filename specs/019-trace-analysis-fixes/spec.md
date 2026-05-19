# SPEC-019 — Trace-Analysis Fixes (architecture-check batch, mono_agent / qwen3-coder:30b)

## Contexto

Análisis exhaustivo de trazas del batch `batch-bugsinpy-architecture-check-20260518T205524Z`
(12 bugs, arquitectura `mono_agent`, modelo `qwen3-coder:30b`). Se identificaron 10 mejoras
concretas en el harness, el runner y la ingeniería de contexto.

## Objetivos

1. **extra_packages**: mecanismo en el harness para pre-instalar paquetes antes de la primera iteración.
2. **Exit-4 context**: inyectar guía de collection-failure en el primer turno cuando `baseline_exit_code == 4`.
3. **Exit-4 run-test relaxation**: permitir una llamada pre-edit a `run_test_target` si el baseline fue exit-4 (para que el agente verifique si `pip install` resolvió el problema).
4. **old_text_not_found enrichment**: añadir `file_size_lines` y `hint` al error para que el agente sepa que debe releer el archivo.
5. **Exclusión de proyectos incompatibles**: keras, matplotlib, sanic — eliminar de architecture-check y del pool de experimento.
6. **max_turns 20 → 30**: el batch architecture-check usaba un límite demasiado bajo para bugs complejos.

## Proyectos excluidos del pool de experimento

| Proyecto    | Razón                                          |
|-------------|------------------------------------------------|
| keras       | Dependencias TensorFlow/GPU, no instalable     |
| matplotlib  | Extensiones C (`ft2font`), build complejo      |
| sanic       | Conflicto `pytest_benchmark` version           |

## Archivos modificados

| Archivo                                              | Cambio                                              |
|------------------------------------------------------|-----------------------------------------------------|
| `src/llm_autofix_agents/batch/config.py`             | `BugEntry.extra_packages` field                     |
| `src/llm_autofix_agents/datasets/bugsinpy.py`        | `_reinstall_bugsinpy_requirements()` + `_install_extra_packages()`  |
| `src/llm_autofix_agents/tools/context.py`            | `baseline_exit_code`, `pre_edit_test_count` fields  |
| `src/llm_autofix_agents/flow/iteration/runner.py`    | Inicialización de los nuevos campos en `_prepare()` |
| `src/llm_autofix_agents/tools/test_tools.py`         | Exit-4 relaxation en `run_test_target`              |
| `src/llm_autofix_agents/flow/policies/iteration.py`  | `_build_exit4_block()` + `_EXIT4_GUIDANCE`          |
| `src/llm_autofix_agents/tools/edit_tools.py`         | `old_text_not_found` error enrichment               |
| `datasets/bugsinpy.yaml`                             | `extra_packages: [testfixtures]` en scrapy-33       |
| `batches/bugsinpy-architecture-check.yaml`           | Excluir keras/matplotlib/sanic, `max_turns: 30`     |
| `docs/experiment-plan.md`                            | Exclusión table, total ~48 bugs, tiempos revisados  |

## Tests añadidos

- `tests/test_config.py::BugEntryExtraPackagesTests` — 3 tests (defaults, accepts list, rejects non-list)
- `tests/test_iteration_input.py::ExitCode4FacadeTests` — 3 tests (hint included, requirements included, exit-1 no hint)
- `tests/test_edit_guardrails.py::FuzzyReplaceTests::test_replace_in_file_not_found_includes_file_size_hint` — 1 test
- `tests/test_apr_tools.py::RunTestTargetExit4RelaxationTests` — 3 tests (allows first, blocks second, exit-1 always blocks)

Total nuevo: **10 tests**, todos passing.
