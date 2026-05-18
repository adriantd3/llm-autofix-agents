# SPEC-018 — Simplificación de estados de run + rediseño de veredictos de validación

## Motivación

Dos problemas detectados antes de iniciar la experimentación formal:

1. **`partial` es un estado fantasma**: se asigna en 4 sitios del flujo pero ningún consumidor
   lo trata de forma diferente a `failed`. No aparece en el resumen de batch (sin emoji, sin
   conteo separado), no hay filtros SQL sobre él. Es ruido semántico sin valor analítico.

2. **Los veredictos del validador mezclan dos dimensiones ortogonales**: `INCORRECT` e
   `INFRA_FAIL` cubren casos donde los tests fallan, pero el validador LLM **sólo debería
   ejecutarse cuando los tests pasan** (`final_status = 'success'`). Con ese filtro, el espacio
   de veredictos se simplifica radicalmente. Además, `INCORRECT` y `PLAUSIBLE` tenían una
   frontera semántica borrosa e indefendible.

## Decisiones

### A — Merge `partial` → `failed`

`RunStatus.PARTIAL` se elimina. Todos los casos que lo producían (agente sin progreso,
agente bloqueado, max_iterations agotado) pasan a `RunStatus.FAILED`.

Justificación: en APR, si los tests no pasan al final del run, el bug no está reparado.
No hay distinción operativa entre "falló porque el agente se bloqueó" y "falló porque el
fix era incorrecto". Ambos son `failed`.

### B — Nuevo conjunto de veredictos de validación

El validador LLM sólo se invoca para runs con `final_status = 'success'`.

| Veredicto | Condición |
|---|---|
| `CORRECT` | Tests pasan Y el fix aborda el mismo root cause que el patch canónico |
| `PLAUSIBLE` | Tests pasan PERO el fix es incompleto, usa un camino diferente al canónico, o no cubre toda la propagación |
| `OVERFITTING` | Tests pasan PERO el fix no resuelve el bug real: modifica tests, hardcodea valores, o adapta el código a las aserciones sin corregir la causa raíz |
| `VALIDATION_ERROR` | El pipeline de validación falló (LLM error, patch canónico no accesible, error inesperado) — se persiste en DB para trazabilidad |

`INCORRECT` e `INFRA_FAIL` se eliminan:
- Los runs con tests fallidos no llegan al validador → `INCORRECT` (tests fail) es redundante
- Los runs con infra rota son `infra_failure` en Layer 1 → `INFRA_FAIL` es redundante
- `VALIDATION_ERROR` reemplaza el skip silencioso en errores de pipeline

### C — `infra_fail_detected` en schema

La columna `infra_fail_detected` en `run_validations` se mantiene en el schema (NULL permanente)
para no necesitar migración. El campo se elimina del código activo.

No se sube `SCHEMA_VERSION`.

## Ficheros afectados

| Fichero | Cambio |
|---|---|
| `contracts.py` | Eliminar `PARTIAL` de `RunStatus` |
| `flow/iteration/decision_enactor.py` | `PARTIAL` → `FAILED` (2 sitios) |
| `flow/strategy.py` | `PARTIAL` → `FAILED` (2 sitios) |
| `batch/runner.py` | Añadir `"partial"` al emoji map (compatibilidad histórica) |
| `validation/models.py` | Nuevo Literal para `verdict`; eliminar `infra_fail_detected` |
| `validation/prompt.py` | System prompt actualizado |
| `validation/runner.py` | Filtrar solo `success`; persistir `VALIDATION_ERROR` en errores |
| `observability/models.py` | Actualizar comentario de `verdict`; `infra_fail_detected` siempre `None` |
| `observability/sqlite_schema.py` | Actualizar vistas: añadir `overfitting_count`, `ever_overfitting`; retirar `infra_fail_detected` de `v_run_summary` |
| `.agents/skills/apr-validator/SKILL.md` | Nuevo decision tree + tabla de veredictos |
| `specs/013-formal-validation/spec.md` | Actualizar tabla de veredictos |
| `docs/experiment-plan.md` | Actualizar sección de validación |
| Tests | Ver tasks.md |
