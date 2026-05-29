# SPEC-013: Validación Formal de Fixes APR

## Metadata
- Fecha: 2026-05-16
- Estado: En curso
- Owner: adriantd3

## Problema

El resultado actual `resolved` (booleano) es insuficiente como métrica de validación formal:

1. **Test overfitting**: el agente puede pasar los tests ajustando el código a las aserciones sin
   resolver el root cause real (plausible patches, APR clásico).
2. **Infra failures**: los tests pueden fallar por problemas de instalación, compilación o entorno,
   no por el código, generando falsos negativos.
3. **Comparabilidad limitada**: sin una señal de calidad del fix, no es posible comparar
   arquitecturas y modelos de forma rigurosa para el TFM.

## Objetivo

Definir un pipeline de validación post-run que produzca un veredicto formal por run, almacenado
en la base de datos relacional existente, y consultable para generar comparativas entre
arquitecturas y modelos.

## Señales del pipeline (3 capas)

```
Run finalizado
     │
     ▼
[1] Test signal        → PASS / FAIL  (determinista, ya existe en `runs.resolved`)
     │
     ▼
[2] Patch comparison   → ¿aborda el mismo root cause que el patch canónico?  (LLM semántico, solo para `success`)
     │
     ▼
[3] Validator verdict  → CORRECT | PLAUSIBLE | OVERFITTING | FAIL  (LLM sintético, solo para `success`)
```

La comparación de patches es **semántica**, no line-by-line. El objetivo no es igualdad textual
sino equivalencia de intención: ¿el agente identificó y corrigió el mismo problema de fondo?

## Veredictos y su semántica

| Veredicto    | Condición                                                                              |
|--------------|----------------------------------------------------------------------------------------|
| `CORRECT`          | Tests pasan Y el fix aborda el mismo root cause que el patch canónico                 |
| `PLAUSIBLE`        | Tests pasan PERO el fix diverge del canónico o no cubre la propagación completa       |
| `OVERFITTING`      | Tests pasan PERO el agente ajustó el código a las aserciones sin corregir el bug real |
| `FAIL`             | Tests no pasan, no hay patch válido, o no aplica validación semántica                 |

> **Nota de diseño**: "Partially correct" se descarta como categoría. La distinción que aporta
> valor para el TFM es CORRECT vs PLAUSIBLE — revela el problema clásico APR de *plausible but
> not correct patches*. Un fix bien encaminado pero incompleto es PLAUSIBLE, no una categoría
> intermedia indefinida.

## Fuentes de ground truth por dataset

| Dataset  | Patch canónico                                              |
|----------|-------------------------------------------------------------|
| QuixBugs | `correct_python_programs/{bug_id}.py` (archivo completo)   |
| BugsInPy | `bug_patch.txt` dentro del workspace del contenedor        |

## Extensión del esquema de datos

Nueva tabla `run_validations` en el SQLite schema existente:

```sql
CREATE TABLE IF NOT EXISTS run_validations (
  validation_id       TEXT PRIMARY KEY,
  run_id              TEXT NOT NULL,
  validated_at        TEXT NOT NULL,
  validator_model     TEXT NOT NULL,

  -- Señales de entrada cacheadas (para reproducibilidad del veredicto)
  test_passed                 INTEGER,   -- 0/1/NULL
  infra_fail_detected         INTEGER,   -- 0/1
  canonical_patch_available   INTEGER,   -- 0/1 (¿había ground truth disponible?)

  -- Veredictos del LLM
  patch_semantically_matches  INTEGER,   -- 0/1/NULL (¿mismo root cause que canónico?)
  verdict                     TEXT NOT NULL,  -- CORRECT|PLAUSIBLE|OVERFITTING|FAIL
  confidence                  REAL,      -- 0.0–1.0
  justification               TEXT,      -- razonamiento del validador

  FOREIGN KEY (run_id) REFERENCES runs(run_id)
);
```

`run_id` → `runs` es la clave de todo: desde `run_id` se accede a
`architecture_id`, `model_configs` (vía `run_agents`), `benchmark_name`, `problem_id`,
`total_tokens`, `total_iterations`. Toda comparativa es una JOIN sobre estas tablas.

## Relaciones clave para consultas TFM

```
architectures (1) ──< runs (N)
model_configs  (1) ──< run_agents >── runs
runs.problem_id           → bug en dataset YAML
runs (1) ──── (0..1) run_validations
runs (1) ──< (N) iterations
```

## Métricas derivadas para el TFM

### Métricas discretas (tablas bug-por-bug)
- `verdict`: `CORRECT | PLAUSIBLE | OVERFITTING | FAIL`
- `test_passed`: boolean directo del sistema
- `patch_semantically_matches`: juicio LLM sobre equivalencia con ground truth

### Métricas continuas (comparativas por arquitectura/modelo)
- `repair_rate = COUNT(verdict='CORRECT') / total_runs`
- `plausible_rate = COUNT(verdict IN ('CORRECT','PLAUSIBLE')) / total_runs`
- `avg_tokens_per_run` → eficiencia del procedimiento
- `avg_iterations_to_fix` → convergencia

> La diferencia `plausible_rate - repair_rate` es el **overfitting gap** de cada arquitectura:
> cuántos bugs "pasan" pero no están realmente reparados. Métrica narrativa central para el TFM.

### Query de referencia para comparativa arquitectura × modelo

```sql
SELECT
  a.name                             AS architecture,
  mc.model                           AS model,
  r.benchmark_name                   AS benchmark,
  r.problem_id                       AS bug,
  COUNT(*)                           AS total_runs,
  SUM(v.verdict = 'CORRECT')         AS correct,
  SUM(v.verdict IN ('CORRECT','PLAUSIBLE')) AS plausible,
  AVG(r.total_tokens)                AS avg_tokens,
  AVG(r.total_iterations)            AS avg_iterations
FROM runs r
JOIN architectures a USING (architecture_id)
JOIN run_agents ra ON ra.run_id = r.run_id AND ra.agent_order = 1
JOIN model_configs mc ON mc.model_config_id = ra.model_config_id
LEFT JOIN run_validations v USING (run_id)
GROUP BY a.name, mc.model, r.benchmark_name, r.problem_id
ORDER BY architecture, model, benchmark, bug;
```

## Diseño del validador como SKILL

El validador se implementa como una SKILL de GitHub Copilot/Claude para garantizar que las
capacidades sean estables independientemente de quién invoque la validación.

### Inputs que recibe siempre
1. `problem_id` y `dataset_type` (quixbugs | bugsinpy)
2. Contenido del archivo buggy original
3. Patch generado por el agente (unified diff)
4. Patch canónico (unified diff o archivo correcto completo), si disponible
5. Output del test (stdout + stderr de la última iteración)
6. `test_exit_code` de la última iteración

### Protocolo de razonamiento (fijo)
1. Leer y entender el código buggy original: ¿qué debería hacer la función?
2. Leer y entender el patch canónico: ¿qué corrigió el desarrollador?
3. Leer y entender el patch del agente: ¿qué hizo el agente?
4. Comparar semánticamente: ¿abordan el mismo root cause?
5. Evaluar señal de tests: ¿PASS / FAIL? (el validador solo recibe runs `success`)
6. Detectar overfitting: ¿el agente ajustó el código a las aserciones del test?
6. Sintetizar veredicto con justificación explícita

### Output estructurado (fijo)
```json
{
  "verdict": "CORRECT|PLAUSIBLE|OVERFITTING|FAIL",
  "confidence": 0.0,
  "test_passed": true,
  "patch_semantically_matches": true,
  "justification": "..."
}
```

## Alcance de esta spec

**Dentro de alcance:**
- Extensión del SQLite schema con `run_validations`
- Extensión de `aggregate.py` para preservar `run_validations` en merges
- SKILL del validador APR
- CLI de validación post-run (`apr-validate`)
- Script/views SQL para métricas TFM

**Fuera de alcance:**
- Modificar el flujo de agente (la validación es post-run, no inline)
- Cambiar el campo `resolved` existente en `runs` (se mantiene como señal rápida)
- Validación automática en tiempo real durante el batch
