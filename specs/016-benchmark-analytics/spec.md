# SPEC-016: Benchmark Analytics — Visualización y Comparación de Arquitecturas

## Metadata
- Fecha: 2026-05-17
- Estado: **Diseño** (sin implementación)
- Owner: adriantd3
- Tipo: observabilidad / análisis

## Contexto

Con el primer benchmark completo sobre QuixBugs ejecutado (155 runs, 4 arquitecturas, mismo modelo), el sistema de observabilidad SQLite tiene datos suficientes para análisis cuantitativo. El objetivo de esta spec es catalogar qué gráficas y agregaciones son posibles con el esquema actual, qué prerrequisitos de datos hay que cubrir antes, y qué preguntas de investigación resuelve cada visualización.

**Arquitecturas evaluadas en el benchmark de referencia (2026-05-17):**
- `mono_agent` — 37 runs, 91.9% resuelto
- `multi_agent_orchestrator` — 39 runs, 92.3% resuelto
- `planner_executor` — 39 runs, 92.3% resuelto
- `multi_agent_handoff` — **descartada**: 0% resuelto, tokens=0, agentes downstream no ejecutan. Ver SPEC-003.

La handoff no se incluirá en análisis futuros.

---

## Prerrequisitos de datos (bloqueantes)

Estas columnas son NULL en el benchmark actual y bloquean las visualizaciones más valiosas.

### P1 — `problem_id` y `benchmark_name` en `runs` (crítico)

**Estado**: NULL en todos los runs actuales.
**Causa**: el batch runner no escribe estos campos al lanzar las runs.
**Bloquea**: todas las visualizaciones por bug (heatmap, Pass@k, dificultad).
**Fix**: el runner debe escribir `problem_id` y `benchmark_name` al insertar cada run.

### P2 — Tokens en arquitecturas multi-agente (importante)

**Estado**: `planner_executor` muestra 0 tokens en el agente `executor`; handoff tenía 0 en todo.
**Causa**: los agentes que no son el punto de entrada principal no propagan métricas de tokens al store.
**Bloquea**: comparación de eficiencia real entre agentes dentro de una arquitectura.
**Fix**: verificar que `update_run_totals()` acumule tokens de todos los agentes del run, no solo del primero.

---

## Catálogo de visualizaciones

### Grupo A — Comparación entre arquitecturas (disponibles ahora)

---

#### A1 — Repair rate por arquitectura

**Pregunta**: ¿Qué arquitectura resuelve más bugs?
**Tipo**: bar chart o dot plot
**Fuente**:
```sql
SELECT a.name, COUNT(*) total, SUM(r.resolved) resolved,
       ROUND(SUM(r.resolved) * 1.0 / COUNT(*), 3) rate
FROM runs r JOIN architectures a USING(architecture_id)
GROUP BY a.name
```
**Ejes**: X = arquitectura, Y = tasa de resolución (0–1)
**Variante**: añadir barras de error si hay múltiples runs del mismo problema (requiere P1).

---

#### A2 — Distribución de final_status

**Pregunta**: ¿Cómo termina cada arquitectura? ¿Falla limpiamente o llega a partial?
**Tipo**: stacked bar (100%)
**Fuente**:
```sql
SELECT a.name, r.final_status, COUNT(*) cnt
FROM runs r JOIN architectures a USING(architecture_id)
GROUP BY a.name, r.final_status
```
**Ejes**: X = arquitectura, Y = % de runs, colores = success / partial / failed
**Insight**: `partial` indica que el agente hizo algo pero no pasó los tests. `failed` es error estructural (timeout, infra). Una arq. con muchos `partial` necesita más iteraciones o mejor prompt; con muchos `failed` hay problemas de infra.

---

#### A3 — Token efficiency scatter

**Pregunta**: ¿Qué arquitectura resuelve más por token gastado?
**Tipo**: scatter plot
**Fuente**:
```sql
SELECT a.name,
       AVG(r.total_tokens) avg_tokens,
       AVG(r.duration_seconds) avg_duration,
       ROUND(SUM(r.resolved) * 1.0 / COUNT(*), 3) rate
FROM runs r JOIN architectures a USING(architecture_id)
WHERE r.total_tokens > 0
GROUP BY a.name
```
**Ejes**: X = avg_tokens, Y = repair_rate, tamaño del punto = avg_duration
**Nota**: excluir handoff (`total_tokens = 0` en todo el batch).

---

#### A4 — Distribución de duración por arquitectura

**Pregunta**: ¿Cuánto tarda en promedio cada arquitectura? ¿Hay outliers?
**Tipo**: box plot o violin
**Fuente**: `SELECT architecture_id, duration_seconds FROM runs`
**Ejes**: X = arquitectura, Y = segundos
**Insight**: planner_executor tiene avg ~87s vs 52s del mono_agent con idéntica tasa de resolución — overhead del plan sin beneficio en este dataset.

---

#### A5 — Distribución de iteraciones

**Pregunta**: ¿Cuántas iteraciones necesita cada arquitectura para resolver?
**Tipo**: box plot o histogram por arquitectura
**Fuente**: `SELECT architecture_id, total_iterations FROM runs`
**Ejes**: X = arquitectura, Y = nº de iteraciones
**Insight**: una arq. que resuelve en 1 iteración es más eficiente; más de 2 iteraciones suele indicar que el primer intento falla y el agente necesita feedback del test.

---

### Grupo B — Herramientas y comportamiento del agente (disponibles ahora)

---

#### B1 — Uso de herramientas por arquitectura (heatmap)

**Pregunta**: ¿Qué herramientas usa cada arquitectura? ¿Con qué frecuencia?
**Tipo**: heatmap (tool_name × architecture, valor = nº llamadas)
**Fuente**:
```sql
SELECT a.name arch, tc.tool_name, COUNT(*) calls
FROM tool_calls tc
JOIN runs r USING(run_id)
JOIN architectures a USING(architecture_id)
GROUP BY a.name, tc.tool_name
ORDER BY calls DESC
```
**Variante**: normalizar por número de runs para comparar densidad de uso.

---

#### B2 — Tasa de éxito por herramienta

**Pregunta**: ¿Qué herramientas fallan más? ¿Dónde hay fricciones en el tool loop?
**Tipo**: bar chart horizontal, ordenado por tasa de éxito
**Fuente**:
```sql
SELECT tool_name,
       COUNT(*) total,
       ROUND(SUM(CASE WHEN success=1 THEN 1 ELSE 0 END) * 1.0 / COUNT(*), 3) success_rate,
       AVG(duration_seconds) avg_duration_s
FROM tool_calls
GROUP BY tool_name ORDER BY total DESC
```
**Insight actual**: `replace_in_file` tiene ~78% de éxito (129/166) — la herramienta de edición más usada falla ~1 de cada 5 veces.

---

#### B3 — Convergencia por iteración

**Pregunta**: ¿En qué iteración suelen resolver los agentes? ¿Mejoran progresivamente?
**Tipo**: line chart o heatmap de densidad
**Fuente**:
```sql
SELECT a.name, i.iteration_index,
       SUM(CASE WHEN i.test_exit_code=0 THEN 1 ELSE 0 END) passed,
       COUNT(*) total
FROM iterations i
JOIN runs r USING(run_id)
JOIN architectures a USING(architecture_id)
GROUP BY a.name, i.iteration_index
```
**Ejes**: X = iteration_index, Y = % de runs que pasan tests en esa iteración
**Insight**: si la mayoría resuelve en iter 1, la política de iteraciones es conservadora; si hay resoluciones en iter 2-3, el feedback loop del test aporta valor.

---

#### B4 — Tokens por agente (arquitecturas multi-agente)

**Pregunta**: ¿Qué agente dentro de cada arquitectura consume más tokens?
**Tipo**: stacked bar por arquitectura
**Fuente**:
```sql
SELECT a.name arch, ra.agent_role,
       AVG(ae.total_tokens) avg_tokens,
       COUNT(ae.agent_execution_id) executions
FROM agent_executions ae
JOIN run_agents ra USING(run_agent_id)
JOIN runs r ON ae.run_id = r.run_id
JOIN architectures a USING(architecture_id)
WHERE ae.total_tokens > 0
GROUP BY a.name, ra.agent_role
```
**Nota**: actualmente útil solo para orchestrator (un agente) y planner. Requiere P2 para planner_executor completo.

---

#### B5 — Timeline de runs (Gantt)

**Pregunta**: ¿Cómo se solaparon los runs en el batch? ¿Hay cuellos de botella?
**Tipo**: Gantt chart
**Fuente**: `started_at`, `finished_at`, `final_status` en `runs`
**Ejes**: Y = run_id (o problem_id cuando esté disponible), X = tiempo absoluto, color = final_status
**Útil para**: detectar runs que se solaparon mal (paralelismo excesivo → CUDA OOM) o que tardaron anormalmente.

---

### Grupo C — Análisis por bug (requiere P1)

Estas visualizaciones están bloqueadas hasta que `problem_id` y `benchmark_name` se escriban en `runs`.

---

#### C1 — Heatmap bug × arquitectura

**Pregunta**: ¿Qué bugs resuelve cada arquitectura? ¿Hay bugs que ninguna resuelve?
**Tipo**: heatmap (bug × arquitectura, color = resolved 0/1)
**Valor**: es el análisis principal para comparar arquitecturas en benchmarks — muestra si la diferencia en tasa agregada se debe a pocos bugs difíciles o a un patrón sistemático.

---

#### C2 — Bugs únicos por arquitectura (diagrama de Venn / upset plot)

**Pregunta**: ¿Qué bugs resuelve una arquitectura que otra no?
**Tipo**: upset plot o tabla de solapamiento
**Valor**: informa si las arquitecturas son complementarias (podrían combinarse) o redundantes.

---

#### C3 — Pass@k por arquitectura

**Pregunta**: si ejecuto k veces la misma arquitectura en el mismo bug, ¿cuántos bugs resuelvo al menos una vez?
**Tipo**: línea (k en X, % bugs resueltos en Y)
**Nota**: requiere múltiples runs por bug × arquitectura. En este benchmark hay 1 run por bug × arquitectura, así que solo tenemos Pass@1.

---

#### C4 — Dificultad del bug vs. recursos consumidos

**Pregunta**: ¿Los bugs más difíciles consumen más tokens/iteraciones?
**Tipo**: scatter (tokens en X, iters en Y, color = resolved)
**Nota**: sin `problem_id` no se puede etiquetar cada punto con el nombre del bug.

---

### Grupo D — Validación formal (requiere ejecutar validator)

La tabla `run_validations` tiene 0 filas en el benchmark actual. Estas visualizaciones requieren pasar por el validador (SPEC-013).

- **D1** — Distribución de veredictos (CORRECT / PLAUSIBLE / INCORRECT / INFRA_FAIL) por arquitectura
- **D2** — Tasa CORRECT vs repair_rate (resolved) — mide cuántos "resueltos" son realmente correctos vs. overfitting a los tests
- **D3** — Confianza del validador vs. veredicto (scatter)

---

## Resumen de prioridades

| ID | Visualización | Estado | Valor |
|----|---|---|---|
| A1 | Repair rate por arquitectura | **Disponible** | Alto |
| A2 | Distribución final_status | **Disponible** | Alto |
| A3 | Token efficiency scatter | **Disponible** | Alto |
| A4 | Duración box plot | **Disponible** | Medio |
| A5 | Iteraciones box plot | **Disponible** | Medio |
| B1 | Tool usage heatmap | **Disponible** | Medio |
| B2 | Tool success rate | **Disponible** | Medio |
| B3 | Convergencia por iteración | **Disponible** | Alto |
| B4 | Tokens por agente | **Parcial** (requiere P2) | Medio |
| B5 | Timeline Gantt | **Disponible** | Bajo |
| C1 | Heatmap bug × arquitectura | **Bloqueado** (requiere P1) | Muy alto |
| C2 | Bugs únicos por arquitectura | **Bloqueado** (requiere P1) | Alto |
| C3 | Pass@k | **Bloqueado** (requiere P1 + múltiples runs) | Alto |
| C4 | Dificultad vs. recursos | **Bloqueado** (requiere P1) | Medio |
| D1-D3 | Validación formal | **Bloqueado** (requiere SPEC-013) | Muy alto |

---

## Notas de implementación

- Las queries de este documento son directamente ejecutables sobre cualquier DB agregada con el aggregator actual.
- La columna correcta es `final_status` (no `status`) — error frecuente en scripts ad-hoc.
- Para las gráficas del Grupo A y B no hace falta modificar el esquema — solo consultar.
- El fix para P1 es en el batch runner / run launcher, no en el schema.
- Librería sugerida para implementación: `matplotlib` / `seaborn` para scripts standalone, o notebooks con `pandas` + `plotly` para exploración interactiva.
