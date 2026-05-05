# Spec 006: Observability Improvement

## Objetivo

Mejorar la observabilidad del sistema sin sobrecomplicarlo, manteniendo el diseño actual basado en `RunObserver`/`CompositeObserver`. La solución debe servir para mono_agent, multi_agent_handoff y preparar el terreno para una futura arquitectura orchestrator/agents-as-tools.

## Contexto

La observabilidad actual usa hooks del SDK (`APRRunHooks`) y observers (`SQLiteObserver`, `MarkdownLiveObserver`, `ConsoleObserver`). El `live.md` es demasiado pobre para depurar runs y comparar arquitecturas. No hay fuente de verdad estructurada por run, los tool calls carecen de duración/argumentos/resultados, y los handoffs no capturan el razonamiento.

## Principios

1. Mantener los hooks actuales; no sustituirlos.
2. Observers solo persisten/renderizan; no formatean Markdown en el runtime.
3. Hooks capturan lifecycle del SDK.
4. Tool wrappers resumen args/result; las tools no conocen observers.
5. JSONL es append-only y fuente de verdad por run. SQLite para consultas agregadas. live.md para lectura humana.
6. Si correlacionar hook y wrapper es costoso, priorizar implementación simple documentada.
7. No introducir OpenTelemetry, dashboards ni dependencias pesadas.
8. Hashes solo donde aporten valor (payloads truncados, código fuente).

## Cambios principales

### P1: JsonlEventObserver

Nuevo observer que escribe en `results/<run_id>/events.jsonl`. Una línea JSON por evento, append-only.

- Event format: `{"event":"tool_call","ts":"...","run_id":"...",...}`
- Todos los campos del record normalizados/truncados. No payloads crudos gigantes.
- Campos grandes resumidos: `args_summary_json`, `result_summary_json`, excerpts, hashes donde aplique.
- Se integra en `CompositeObserver` vía `build_observer` cuando `config.enabled`.
- Config: `jsonl_enabled: bool = True` en `ObservabilityConfig`.

### P2: Agente y duración en live.md

`MarkdownLiveObserver.on_tool_call` muestra:
- `tool 001: [patcher] replace_in_file -> success (0.007s)` cuando duración disponible
- `tool 001: [baseline] read_file -> success` sin duración
- `tool 001: read_file -> success` sin agente

### P3: Result summaries parseando on_tool_end

Nueva utilidad `summarize_tool_result(tool_name, result_json) -> dict` con extracción específica por tool:

| Tool | Campos extraídos |
|---|---|
| read_file | path, start_line, end_line, line_count, truncated, content_chars, content_hash |
| search_files | pattern, glob, returned, scanned_files, top_paths (first 5) |
| replace_in_file | path, replaced, bytes_written, old_hash, new_hash, error? |
| replace_lines | path, start_line, end_line, error? |
| write_file | path, bytes_written |
| execute_command / run_test_target | command (truncado), cwd, exit_code, timed_out, stdout_chars, stderr_chars, target?, runner?, tool? |
| git_status_summary | ok, branch, changed_files, truncated |
| git_diff_summary | ok, pathspec, patch_truncated |
| list_files | glob, returned, total_seen, truncated |
| get_workspace_info | ok, root_dir |
| apply_unified_diff | ok, path?, error? |

Strings > 500 chars truncados con `... [truncated]`. Hashes SHA-256[:16].

### P4: IDs estables para tool calls

Reemplazar `f"{agent_execution_id}-tool{seq:03d}"` por `f"tc-{uuid.uuid4().hex[:12]}"`. El campo `seq` sigue como counter informativo per-iteration, no como parte del ID.

### P5: ToolCallRecord enriquecido + migración SQLite v4→v5

Nuevos campos opcionales en `ToolCallRecord`:

```
run_agent_id: str | None = None
started_at: str | None = None
finished_at: str | None = None
duration_seconds: float | None = None
args_summary_json: str | None = None
result_summary_json: str | None = None
result_excerpt: str | None = None
error_type: str | None = None
error_message_short: str | None = None
```

APRRunHooks: `on_tool_start` registra `started_at`; `on_tool_end` computa `duration_seconds`, `finished_at`, `result_summary_json`, `result_excerpt`, `error_type`/`error_message_short`, `run_agent_id` desde `self._run_agent_ids`.

Migración SQLite v4→v5: ALTER TABLE `tool_calls` ADD COLUMN para cada campo nuevo + `handoff_note_json TEXT` en `agent_handoffs`.

### P6: Handoff notes con input_type/on_handoff

Modelo `APRHandoffNote` (Pydantic):

```
summary: str
evidence: list[str]
suspected_files: list[str]
next_focus: str | None
confidence: float | None
```

En `handoff.py`: usar `handoff(agent, input_type=APRHandoffNote, on_handoff=callback)` para triage→localizer, localizer→patcher, patcher→validator.

El callback `on_handoff` almacena la nota en `contextvars.ContextVar`. `APRRunHooks.on_handoff` la lee y la añade a `AgentHandoffRecord.handoff_note_json`.

No poner `output_schema` en agentes intermedios.

### P7: Wrapper observable para args_summary

`make_observable(tool: FunctionTool) -> FunctionTool` en `tools/observable.py`:

- Envuelve `on_invoke_tool` para capturar args antes de la invocación.
- Almacena `args_summary_json` en `contextvars.ContextVar` (`current_tool_args`).
- `APRRunHooks.on_tool_end` lee el context var y lo añade a `ToolCallRecord`.
- Se aplica en `build_apr_tools()` en `profiles.py`.
- La tool no conoce observers, SQLite, JSONL ni live.md.

Utilidad `summarize_tool_args(tool_name, parsed_args) -> dict` con extracción específica por tool (paths, hashes para contenido largo, comandos truncados).

### Context variables compartidos

`observability/tool_context.py`:
- `current_tool_args: ContextVar[dict | None]` — args_summary del tool wrapper
- `pending_handoff_note: ContextVar[dict | None]` — nota del handoff callback

## Flujo de observers

```
CompositeObserver -> SQLiteObserver + JsonlEventObserver + MarkdownLiveObserver + ConsoleObserver
```

`build_observer` instancia `JsonlEventObserver` cuando `config.enabled` y `config.jsonl_enabled`.

## Criterios de aceptación

Una run debe producir:
- `results/<run_id>/events.jsonl` como traza estructurada append-only.
- `results/<run_id>/live.md` legible en tiempo real, con agente por tool, handoffs enriquecidos, duraciones y resultados resumidos.
- `observability.db` con campos consultables para runs/agents/iterations/tools/tests/handoffs.
- `summary.json` final compacto.

La ejecución APR no debe cambiar funcionalmente: solo mejora la trazabilidad.

## No incluido

- OpenTelemetry, dashboards, dependencias externas.
- Modificación del comportamiento de ejecución del agente.
- `output_schema` en agentes intermedios (solo handoff notes).
- Hashes en todos los campos (solo donde aporten valor).

## Archivos nuevos

| Archivo | Propósito |
|---|---|
| `observability/jsonl_observer.py` | JsonlEventObserver |
| `observability/tool_summaries.py` | summarize_tool_result(), summarize_tool_args() |
| `observability/tool_context.py` | ContextVars para tool args y handoff notes |
| `tools/observable.py` | make_observable() wrapper para FunctionTool |

## Archivos modificados

| Archivo | Cambios |
|---|---|
| `observability/models.py` | ToolCallRecord enriquecido, APRHandoffNote, handoff_note_json en AgentHandoffRecord |
| `observability/lifecycle_hooks.py` | on_tool_start registra started_at, on_tool_end genera summaries, on_handoff lee handoff note |
| `observability/interactive.py` | MarkdownLiveObserver muestra [agent] y duración en tool calls, handoff notes |
| `observability/sqlite_schema.py` | MIGRATION_V4_TO_V5, SCHEMA_VERSION=5 |
| `observability/sqlite_store.py` | insert_tool_call con nuevos campos, insert_agent_handoff con handoff_note_json |
| `observability/config.py` | jsonl_enabled en ObservabilityConfig |
| `observability/__init__.py` | Exports nuevos |
| `flow/lifecycle/observer_factory.py` | Añadir JsonlEventObserver al composite |
| `architectures/handoff.py` | handoff() con input_type=APRHandoffNote y on_handoff callback |
| `tools/profiles.py` | build_apr_tools() envuelve con make_observable() |

## Migración SQLite v4→v5

| Tabla | Columna | Tipo |
|---|---|---|
| tool_calls | run_agent_id | TEXT |
| tool_calls | started_at | TEXT |
| tool_calls | finished_at | TEXT |
| tool_calls | duration_seconds | REAL |
| tool_calls | args_summary_json | TEXT |
| tool_calls | result_summary_json | TEXT |
| tool_calls | result_excerpt | TEXT |
| tool_calls | error_type | TEXT |
| tool_calls | error_message_short | TEXT |
| agent_handoffs | handoff_note_json | TEXT |