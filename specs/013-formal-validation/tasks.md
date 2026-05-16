# TASKS SPEC-013: Validación Formal de Fixes APR

## Estado global
- Spec: SPEC-013
- Subhito activo: —
- Estado: Completado

---

## VL1 — Extensión del esquema SQLite ✅

### Objetivo
Añadir la tabla `run_validations` al schema existente y bumpar `SCHEMA_VERSION`.

### Tasks
- [x] VL1-T01 Añadir `CREATE TABLE run_validations` a `sqlite_schema.py` con FK a `runs`
- [x] VL1-T02 Bumpar `SCHEMA_VERSION` (6 → 7) + añadir `MIGRATION_V6_TO_V7`
- [x] VL1-T03 Añadir método `upsert_run_validation` a `SQLiteObservabilityStore`
- [x] VL1-T04 Añadir modelo `RunValidationRecord` a `observability/models.py`
- [x] VL1-T05 Tests unitarios del schema y del método `upsert_run_validation`

---

## VL2 — Extensión de aggregate / merge_from ✅

### Objetivo
Preservar los datos de `run_validations` cuando se hace merge de múltiples batch DBs.

### Tasks
- [x] VL2-T01 Añadir `run_validations` a la lista de tablas en `merge_from` (`sqlite_store.py`)
- [x] VL2-T02 Test: merge de dos DBs con validaciones produce el agregado correcto sin duplicados

---

## VL3 — SKILL del validador APR ✅

### Objetivo
Crear la SKILL del validador APR en `.agents/skills/apr-validator/SKILL.md` con protocolo fijo
de razonamiento, inputs, output estructurado y guías para casos edge.

### Tasks
- [x] VL3-T01 Definir la estructura del SKILL siguiendo las convenciones del proyecto
- [x] VL3-T02 Especificar inputs exactos (con formato para cada tipo de dataset)
- [x] VL3-T03 Definir protocolo de razonamiento (6 pasos)
- [x] VL3-T04 Definir árbol de decisión de veredictos (CORRECT/PLAUSIBLE/INCORRECT/INFRA_FAIL)
- [x] VL3-T05 Definir casos edge: patch canónico no disponible, test timeout, multifile patch

---

## VL4 — CLI de validación post-run (`autofix validate`) ✅

### Objetivo
Implementar un comando CLI que, dado un `--db` o `--batch-dir`, cargue artefactos del run,
invoque el validador LLM y almacene los veredictos en la DB.

### Tasks
- [x] VL4-T01 Añadir subcomando `validate` a `main.py` con args: `--db/--batch-dir`, `--run-id`,
             `--canonical-root`, `--provider`, `--model`, `--force`, `--create-views`
- [x] VL4-T02 Módulo `validation/canonical.py`: resolución del patch canónico por dataset type
- [x] VL4-T03 Módulo `validation/models.py`: `ValidatorOutput` (Pydantic) + `RunValidationInput`
- [x] VL4-T04 Módulo `validation/prompt.py`: system prompt + user prompt builder
- [x] VL4-T05 Módulo `validation/runner.py`: `ValidationRunner` (load → prompt → LLM → store)
- [x] VL4-T06 `llm/agent_factory.py`: función pública `build_model` para uso externo
- [x] VL4-T07 Output CLI: tabla resumen con run_id, verdict, confidence, justification

---

## VL5 — Queries y vistas SQL para métricas TFM ✅

### Objetivo
Proporcionar vistas SQL listas para el análisis del TFM cubriendo las métricas clave.

### Tasks
- [x] VL5-T01 `ANALYSIS_VIEWS_SQL` en `sqlite_schema.py`: `v_run_summary`, `v_architecture_metrics`, `v_bug_heatmap`
- [x] VL5-T02 `SQLiteObservabilityStore.create_analysis_views()`: crea las vistas en cualquier DB
- [x] VL5-T03 `scripts/analysis-views.sql`: script SQL de referencia con vistas + queries de ejemplo
- [x] VL5-T04 Tests: `create_analysis_views` crea las 3 vistas correctamente

---

## VL1 — Extensión del esquema SQLite

### Objetivo
Añadir la tabla `run_validations` al schema existente y bumpar `SCHEMA_VERSION`.

### Tasks
- [ ] VL1-T01 Añadir `CREATE TABLE run_validations` a `sqlite_schema.py` con FK a `runs`
- [ ] VL1-T02 Bumpar `SCHEMA_VERSION` (actualmente 6 → 7)
- [ ] VL1-T03 Añadir método `upsert_run_validation` a `SQLiteObservabilityStore`
- [ ] VL1-T04 Añadir modelo `RunValidationRecord` a `observability/models.py`
- [ ] VL1-T05 Tests unitarios del schema y del método `upsert_run_validation`

### Done cuando
- La tabla existe en una DB inicializada y se puede insertar/actualizar un registro de validación
  con `upsert_run_validation` sin error.

---

## VL2 — Extensión de aggregate.py

### Objetivo
Preservar los datos de `run_validations` cuando se hace merge de múltiples batch DBs.

### Tasks
- [ ] VL2-T01 Identificar las tablas que `merge_from` copia actualmente en `aggregate.py`
- [ ] VL2-T02 Añadir `run_validations` a la lista de tablas mergeadas
- [ ] VL2-T03 Test: merge de dos DBs con validaciones produce el agregado correcto sin duplicados

### Done cuando
- Un `aggregate.py` sobre dos batch DBs con validaciones distintas produce un DB combinado
  correcto.

---

## VL3 — SKILL del validador APR

### Objetivo
Crear la SKILL del validador APR en `.agents/skills/apr-validator/SKILL.md` con protocolo fijo
de razonamiento, inputs, output estructurado y guías para casos edge.

### Tasks
- [ ] VL3-T01 Definir la estructura del SKILL siguiendo las convenciones del proyecto
- [ ] VL3-T02 Especificar inputs exactos (con formato para cada tipo de dataset)
- [ ] VL3-T03 Definir protocolo de razonamiento (6 pasos: código primero, canónico, generado,
             comparación semántica, test signal, veredicto)
- [ ] VL3-T04 Definir árbol de decisión de veredictos (CORRECT/PLAUSIBLE/INCORRECT/INFRA_FAIL)
- [ ] VL3-T05 Definir casos edge: patch canónico no disponible, test timeout, multifile patch

### Done cuando
- El SKILL puede ser invocado por Copilot con los inputs de un run real y produce un veredicto
  estructurado coherente con la semántica de la spec.

---

## VL4 — CLI de validación post-run (`apr-validate`)

### Objetivo
Implementar un comando CLI que, dado un `run_id` (o un directorio de batch), cargue los
artefactos del run, invoque el validador y almacene el veredicto en la DB.

### Tasks
- [ ] VL4-T01 Definir interfaz CLI: `uv run apr-validate --run-id <id> --db <path>`
             y variante batch: `uv run apr-validate --batch-dir <path>`
- [ ] VL4-T02 Implementar carga de artefactos del run desde DB + paths de artefactos
             (`diff_path`, `live_log_path`, canonical patch derivado de `problem_id`)
- [ ] VL4-T03 Implementar resolución del patch canónico por dataset type + problem_id
- [ ] VL4-T04 Implementar llamada al LLM validador con el SKILL (prompt builder)
- [ ] VL4-T05 Implementar escritura del veredicto a `run_validations` vía `upsert_run_validation`
- [ ] VL4-T06 Output CLI: tabla resumen con run_id, verdict, confidence por run procesado
- [ ] VL4-T07 Tests de integración del CLI con mocks del LLM

### Done cuando
- `uv run apr-validate --batch-dir results/batch-X` procesa todos los runs del batch,
  escribe veredictos en la DB y muestra un resumen por consola.

---

## VL5 — Queries y vistas SQL para métricas TFM

### Objetivo
Proporcionar un conjunto de vistas SQL o un script de consultas listo para usar en el análisis
del TFM, cubriendo las métricas clave de comparativa.

### Tasks
- [ ] VL5-T01 Vista `v_run_summary`: JOIN de `runs`, `architectures`, `model_configs`,
             `run_validations` con todas las columnas relevantes en una fila por run
- [ ] VL5-T02 Vista `v_architecture_metrics`: `repair_rate`, `plausible_rate`, `avg_tokens`,
             `avg_iterations` agrupados por architecture + model + benchmark
- [ ] VL5-T03 Vista `v_bug_heatmap`: matriz architecture × bug con verdict (para tabla del TFM)
- [ ] VL5-T04 Documentar las vistas en un README o script SQL dentro de `scripts/`
- [ ] VL5-T05 Validar las vistas sobre un DB de análisis real con al menos 2 arquitecturas

### Done cuando
- Las vistas producen resultados correctos sobre un DB de análisis real y son suficientes para
  generar las gráficas y tablas planificadas en el TFM sin joins manuales adicionales.
