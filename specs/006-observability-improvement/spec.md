# Spec 006: Observability Improvement

## Objetivo

Mejorar la observabilidad del sistema sin sobrecomplicarlo, manteniendo el diseño actual basado en `RunObserver`/`CompositeObserver`. La solución sirve para mono_agent, multi_agent_handoff y prepara el terreno para orchestrator/agents-as-tools.

## Cambios implementados

### P1: JsonlEventObserver
- Nuevo `observability/jsonl_observer.py`: escribe en `results/<run_id>/events.jsonl`, una línea JSON por evento.
- Integrado en `CompositeObserver` vía `build_observer` cuando `config.jsonl_enabled=True` (default).
- Config: `jsonl_enabled: bool = True` en `ObservabilityConfig`.

### P2: Agente y duración en live.md
- `MarkdownLiveObserver.on_tool_call` muestra `tool 001: [patcher] read_file -> success (0.007s)`.
- `ConsoleObserver.on_tool_call` usa el mismo formato.

### P3: Result summaries parseando on_tool_end
- Nuevo `observability/tool_summaries.py`: `summarize_tool_result()` con extracción específica por tool (read_file, search_files, replace_in_file, etc.).
- Hashes SHA-256[:16] para contenido grande, truncación a 500 chars.

### P4: IDs estables para tool calls
- `tool_call_id` cambió de `f"{agent_execution_id}-tool{seq:03d}"` a `f"tc-{uuid.uuid4().hex[:12]}"`.
- `seq` sigue como counter informativo per-iteration.

### P5: ToolCallRecord enriquecido + SQLite v4→v5
- 9 campos nuevos en `ToolCallRecord`: `run_agent_id`, `started_at`, `finished_at`, `duration_seconds`, `args_summary_json`, `result_summary_json`, `result_excerpt`, `error_type`, `error_message_short`.
- `on_tool_start` registra `started_at`; `on_tool_end` computa `duration_seconds`, result summaries, error info.
- Migración SQLite v4→v5: ALTER TABLE para `tool_calls` (9 columnas) + `agent_handoffs` (`handoff_note_json`).

### P6: Handoff notes con input_type/on_handoff
- `APRHandoffInput` (Pydantic BaseModel): `summary`, `evidence`, `suspected_files`, `next_focus`, `confidence`.
- `handoff()` en `handoff.py` usa `input_type=APRHandoffInput, on_handoff=_on_handoff_with_note` para todos los handoffs (triage→localizer, localizer→patcher, patcher→validator).
- `_on_handoff_with_note` almacena nota en `pending_handoff_note` context var.
- `APRRunHooks.on_handoff` lee nota y la añade a `AgentHandoffRecord.handoff_note_json`.
- `MarkdownLiveObserver` muestra handoff notes: summary, suspected_files, confidence.

### P7: Wrapper observable para args_summary
- Nuevo `tools/observable.py`: `make_observable(tool: FunctionTool) -> FunctionTool` envuelve `on_invoke_tool` para capturar args.
- `observability/tool_context.py`: `current_tool_args` y `pending_handoff_note` ContextVars.
- `observability/tool_summaries.py`: `summarize_tool_args()` con extracción por tool.
- `build_apr_tools()` en `profiles.py` envuelve todos los tools con `make_observable`.
- `APRRunHooks.on_tool_end` lee `current_tool_args` para `args_summary_json`.

### P8: Facade input event
- Nuevo `FacadeInputRecord` (dataclass): `run_id`, `iteration_id`, `iteration_index`, `input_text`, `occurred_at`.
- `RunObserver.on_facade_input` añadido al protocolo; implementado en `NullObserver`, `CompositeObserver`, `MarkdownLiveObserver`, `ConsoleObserver`, `JsonlEventObserver`.
- `SQLiteObserver.on_facade_input` es no-op intencional: **no se persiste en SQLite**.
- `IterationTelemetry.record_facade_input(input_text: str)` emite el evento.
- `IterationRunner` emite el evento inmediatamente después de construir `agent_context.user_input`.
- `MarkdownLiveObserver` renderiza el texto completo en un bloque de código markdown.
- `JsonlEventObserver` escribe el JSON completo en `events.jsonl` con `"event": "facade_input"`.
- `ConsoleObserver` loguea truncado a 200 caracteres.

## Archivos nuevos
- `observability/jsonl_observer.py`
- `observability/tool_summaries.py`
- `observability/tool_context.py`
- `tools/observable.py`

## Archivos modificados
- `observability/models.py`: ToolCallRecord enriquecido, APRHandoffNote, AgentHandoffRecord.handoff_note_json
- `observability/lifecycle_hooks.py`: UUID tool_call_id, started_at, duration, summaries, handoff note
- `observability/interactive.py`: Formato enriquecido en live.md y console
- `observability/config.py`: jsonl_enabled
- `observability/__init__.py`: Nuevos exports
- `observability/sqlite_schema.py`: SCHEMA_VERSION=5, MIGRATION_V4_TO_V5
- `observability/sqlite_store.py`: insert_tool_call con 9 campos nuevos, insert_agent_handoff con handoff_note_json
- `flow/lifecycle/observer_factory.py`: JsonlEventObserver en composite
- `architectures/handoff.py`: APRHandoffInput, handoff con input_type/on_handoff
- `tools/profiles.py`: make_observable wrap

## Tests
- 209 tests pasando (13 nuevos sobre los 196 previos)
- Coverage: JsonlEventObserver, MarkdownLiveObserver enriquecido, ToolCallRecord enriquecido, SQLite v5 schema/migration, tool summaries, handoff notes