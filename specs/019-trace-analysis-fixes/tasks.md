# SPEC-019 Tasks

## Estado: COMPLETADO

## Tareas

- [x] **T1**: `BugEntry.extra_packages: list[str]` en `batch/config.py`
- [x] **T2**: `BugsInPyAdapter._install_extra_packages()` en `datasets/bugsinpy.py`
- [x] **T3**: `extra_packages: [testfixtures]` en scrapy-33 (`datasets/bugsinpy.yaml`)
- [x] **T4**: `baseline_exit_code` y `pre_edit_test_count` en `APRToolContext` (`tools/context.py`)
- [x] **T5**: Inicialización en `runner._prepare()` (`flow/iteration/runner.py`)
- [x] **T6**: Exit-4 relaxation en `run_test_target` (`tools/test_tools.py`)
- [x] **T7**: `_build_exit4_block()` + `_EXIT4_GUIDANCE` en `flow/policies/iteration.py`
- [x] **T8**: `old_text_not_found` enrichment con `file_size_lines` + `hint` (`tools/edit_tools.py`)
- [x] **T9**: Actualizar `batches/bugsinpy-architecture-check.yaml` (excluir 3 bugs, `max_turns: 30`)
- [x] **T10**: Actualizar `docs/experiment-plan.md` (exclusión table, pool ~48 bugs)
- [x] **T11**: Tests (10 nuevos tests en 4 archivos, todos passing)
- [x] **T12**: SPEC-019 + `specs/status.md`
