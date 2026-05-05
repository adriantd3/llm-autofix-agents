# Tasks — Spec 006: Observability Improvement

## Prioridad de implementación

Las tasks se implementan en orden de prioridad. Cada task debe passar tests antes de avanzar.

---

### T01: Context variables compartidos + enriquecimiento de modelos

**Archivos**: `observability/tool_context.py` (nuevo), `observability/models.py`

- Crear `observability/tool_context.py` con `current_tool_args: ContextVar[dict | None]` y `pending_handoff_note: ContextVar[dict | None]`.
- Añadir campos opcionales a `ToolCallRecord`: `run_agent_id`, `started_at`, `finished_at`, `duration_seconds`, `args_summary_json`, `result_summary_json`, `result_excerpt`, `error_type`, `error_message_short`.
- Añadir `APRHandoffNote` como dataclass frozen con `summary`, `evidence`, `suspected_files`, `next_focus`, `confidence`.
- Añadir `handoff_note_json: str | None = None` a `AgentHandoffRecord`.
- Actualizar `observability/__init__.py` con nuevos exports.

**Validación**: `uv run python -m pytest tests/test_observability.py -x` pasa. Imports no rotos.

---

### T02: Utilidades de resumen de tools

**Archivos**: `observability/tool_summaries.py` (nuevo)

- Implementar `summarize_tool_result(tool_name: str, result: str) -> dict[str, Any]`:
  - Intenta `json.loads(result)`. Si falla, retorna `{ok: None, error_summary: result[:200]}`.
  - Por cada tool name, extraer campos específicos (ver spec P3).
  - Strings > 500 chars truncadas con `... [truncated]`.
  - Hashes SHA-256[:16] para contenido grande (read_file content, replace_in_file old/new).
- Implementar `summarize_tool_args(tool_name: str, parsed_args: dict) -> dict[str, Any]`:
  - Por cada tool name, extraer campos relevantes (paths, comandos truncados, hashes de contenido largo).
  - Para `replace_in_file`: `old_hash` en vez de `old` completo.
  - Para `write_file`: `content_length` en vez de `content` completo.
  - Para `execute_command`/`run_test_target`: comando truncado a 200 chars si es largo.

**Validación**: Tests unitarios para cada tool type con payloads reales y edge cases (JSON inválido, None, payloads vacíos).

---

### T03: JsonlEventObserver

**Archivos**: `observability/jsonl_observer.py` (nuevo), `observability/config.py`, `flow/lifecycle/observer_factory.py`, `observability/__init__.py`

- Implementar `JsonlEventObserver(results_dir: Path, run_id: str)`:
  - `__init__`: crea `results/<run_id>/` dir.
  - Cada `on_*` method serializa el record a JSON (`json.dumps` con `separators=(",",":")`) y escribe una línea append.
  - Cada línea incluye `"event": "tool_call"` / `"event": "agent_handoff"` etc., `"ts": utc_now_iso()`, y todos los campos del record.
  - Campos grandes ya normalizados (no payloads crudos).
  - `_append()` abre archivo en modo append por evento (mismo patrón que MarkdownLiveObserver).
- Añadir `jsonl_enabled: bool = True` a `ObservabilityConfig` en `config.py`.
- Modificar `build_observer()` para añadir `JsonlEventObserver` cuando `config.enabled` y `config.jsonl_enabled`.
- Exportar desde `__init__.py`.

**Validación**: Test unitario que instancia `JsonlEventObserver`, emite eventos, y verifica que el archivo JSONL tiene líneas válidas parseables como JSON con los campos esperados.

---

### T04: IDs estables para tool calls + enriquecimiento de lifecycle_hooks

**Archivos**: `observability/lifecycle_hooks.py`

- Reemplazar generación de `tool_call_id` de `f"{agent_execution_id}-tool{seq:03d}"` a `f"tc-{uuid.uuid4().hex[:12]}"`.
- En `on_tool_start`: registrar `started_at = utc_now_iso()` en `self._tool_started_at` (dict de seq→timestamp).
- En `on_tool_end`:
  - Obtener `started_at` desde `self._tool_started_at` (limpiar después).
  - Calcular `duration_seconds`.
  - Llamar `summarize_tool_result(tool_name, result)` para `result_summary_json`.
  - Extraer `result_excerpt` (primeros 200 chars del result).
  - Leer `current_tool_args.get()` para `args_summary_json`.
  - Resolver `run_agent_id` desde `self._run_agent_ids`.
  - Determinar `error_type` y `error_message_short` si `success` es False.
  - Crear `ToolCallRecord` con todos los campos nuevos.
- Importar `summarize_tool_result` desde `tool_summaries`.
- Importar `current_tool_args` desde `tool_context`.

**Validación**: Tests existentes de observability pasan. Tool IDs son únicos.

---

### T05: MarkdownLiveObserver enriquecido

**Archivos**: `observability/interactive.py`

- `MarkdownLiveObserver.on_tool_call`: mostrar `[agent_name]` y `(duration_seconds)` si disponibles.
  - Formato: `tool {seq:03d}: [{agent_name}] {tool_name} -> {status} ({duration:.3f}s)`
  - Sin agente: `tool {seq:03d}: {tool_name} -> {status}`
  - Sin duración: sin-parentesis-de-duración.
- `MarkdownLiveObserver.on_agent_handoff`: si `handoff_note_json` no es None, parsear y mostrar:
  ```
  - handoff: localizer -> patcher (at 2026-...)
    - summary: ...
    - suspected_files: [...]
    - confidence: 0.85
  ```
  Sin nota: formato actual sin cambios.
- `ConsoleObserver.on_tool_call`: mostrar `[{agent_name}]` y duración igual que live.md.

**Validación**: Tests unitarios verifican formato de salida en live.md. Extender `test_interactive_observer.py`.

---

### T06: SQLite migration v4→v5 + store update

**Archivos**: `observability/sqlite_schema.py`, `observability/sqlite_store.py`

- Añadir `MIGRATION_V4_TO_V5` con ALTER TABLE para los 9 campos nuevos en `tool_calls` y `handoff_note_json` en `agent_handoffs`.
- Bump `SCHEMA_VERSION = 5`.
- Actualizar `SCHEMA_SQL` con las columnas nuevas para fresh installs.
- Actualizar `SQLiteObservabilityStore.insert_tool_call()` con los nuevos campos.
- Actualizar `SQLiteObservabilityStore.insert_agent_handoff()` con `handoff_note_json`.
- Actualizar `initialize()` para correr migración v4→v5 cuando `user_version < 5`.

**Validación**: `test_observability.py` — test fresh install crea v5, test migración v4→v5 preserva datos existentes, nuevos campos insertan correctamente.

---

### T07: Tool wrapper observable (make_observable)

**Archivos**: `tools/observable.py` (nuevo), `tools/profiles.py`

- Crear `tools/observable.py` con `make_observable(tool: FunctionTool) -> FunctionTool`:
  - Envuelve `tool.on_invoke_tool` para capturar args antes de invocación.
  - Llama `summarize_tool_args(tool.name, parsed_args)` y almacena en `current_tool_args`.
  - Limpia context var después de la invocación (en finally).
  - Retorna nuevo `FunctionTool` con el mismo name, description, schema pero con el wrapper.
- Modificar `build_apr_tools()` en `profiles.py`:
  - Importar `make_observable` y `FunctionTool`.
  - Aplicar `make_observable(t) if isinstance(t, FunctionTool) else t` para cada tool.

**Validación**: Test unitario que verifica que make_observable preserva el FunctionTool original y que context var se establece/limpia correctamente. Verificar que build_apr_tools("full") retorna tools observables.

---

### T08: Handoff notes con input_type/on_handoff

**Archivos**: `architectures/handoff.py`, `observability/lifecycle_hooks.py`, `observability/tool_context.py`

- Definir `APRHandoffNote(BaseModel)` como Pydantic model en `models.py` (no dataclass, porque SDK lo parsea).
- Crear función `make_handoff_observer_callback()` que retorna un callback async para `on_handoff`:
  ```python
  async def on_handoff_callback(ctx, note: APRHandoffNote):
      pending_handoff_note.set(note.model_dump())
  ```
- En `handoff.py`:
  - Reemplazar `handoff(localizer_agent)` con `handoff(localizer_agent, input_type=APRHandoffNote, on_handoff=on_handoff_callback)` para cada handoff.
  - Mantener `output_schema=None` en triage, localizer, patcher (solo validator tiene output_schema).
- En `APRRunHooks.on_handoff`:
  - Leer `pending_handoff_note.get()` y serializar a JSON para `AgentHandoffRecord.handoff_note_json`.
  - Limpiar context var después de leer.

**Validación**: Test unitario que verifica que APRHandoffNote se serializa/deserializa correctamente. Test de integración (si es posible sin LLM) que on_handoff callback almacena la nota en context var.

---

### T09: Integración end-to-end y tests de regresión

**Archivos**: Tests varios

- Verificar que una run mono_agent produce:
  - `results/<run_id>/events.jsonl` con líneas JSON válidas.
  - `results/<run_id>/live.md` con agente, duración y summaries.
  - `observability.db` con campos nuevos consultables.
  - `summary.json` sin cambios funcionales.
- Verificar que una run multi_agent_handoff produce handoff notes en JSONL y live.md.
- Verificar que tools existentes funcionan sin cambios funcionales.
- Verificar que SQLite migration v4→v5 no rompe bases existentes.
- Verificar que `make_observable` no altera el comportamiento de las tools.
- Ejecutar suite completa: `uv run python -m pytest tests/ -x`
- Ejecutar lint: `uv run ruff check src/`

**Validación**: Todos los tests pasan. Lint limpio. Una run de prueba mono_agent completa sin errores de observabilidad.