# SPEC-018 Tasks

## Fase A — Merge `partial` → `failed`

- [x] A1 `contracts.py`: eliminar `PARTIAL = "partial"` de `RunStatus`
- [x] A2 `flow/iteration/decision_enactor.py`: `RunStatus.PARTIAL` → `RunStatus.FAILED` (stop_no_progress y stop_agent_stuck)
- [x] A3 `flow/strategy.py`: `RunStatus.PARTIAL` → `RunStatus.FAILED` (IterationStrategy y PhasedIterationStrategy)
- [x] A4 `batch/runner.py`: añadir `"partial"` al emoji map como `"-"` (compatibilidad histórica)
- [x] A5 Tests: no había assertions que esperaran `"partial"` como status

## Fase B — Rediseño de veredictos de validación

- [x] B1 `validation/models.py`: `Literal["CORRECT", "PLAUSIBLE", "OVERFITTING", "VALIDATION_ERROR"]`; eliminar `infra_fail_detected`
- [x] B2 `validation/prompt.py`: system prompt con nuevos veredictos + nota de contexto
- [x] B3 `validation/runner.py`: `_query_run_ids()` filtra `final_status = 'success'`; errores de pipeline → persistir `VALIDATION_ERROR`; eliminar `infra_fail_detected` de `_build_record`
- [x] B4 `observability/models.py`: comentario de `verdict`; `infra_fail_detected` siempre `None`
- [x] B5 `observability/sqlite_schema.py`: actualizar `ANALYSIS_VIEWS_SQL` (añadir `overfitting_count`, `ever_overfitting`; quitar `infra_fail_detected` de `v_run_summary`)

## Fase C — Documentación y SKILL

- [x] C1 `.agents/skills/apr-validator/SKILL.md`: nuevo decision tree + tabla de veredictos
- [x] C2 `specs/013-formal-validation/spec.md`: actualizar tabla de veredictos
- [x] C3 `docs/experiment-plan.md`: actualizar sección de validación
- [x] C4 `specs/status.md`: registrar SPEC-018 en curso

## Fase D — Tests

- [x] D1 `tests/unit/.../test_validation.py`: actualizar keywords del system prompt; actualizar test que usa `INFRA_FAIL`
- [x] D2 `tests/unit/.../test_validation_schema.py`: cambiar casos con `INFRA_FAIL` → `VALIDATION_ERROR`/`OVERFITTING`
- [x] D3 No había tests con status `"partial"`

## Verificación

- [x] V1 `uv run pytest` — 28 passed, 0 regressions
- [ ] V2 Actualizar `specs/status.md` como completado
