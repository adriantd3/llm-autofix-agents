Aquí tienes el **plan de implementación completo**, ya ajustado a todo lo que hemos decidido:

* SQLite local en vez de MongoDB.
* Observabilidad simple, no perfecta.
* Separación clara entre capa interactiva y capa analítica.
* Tiempos solo por run, iteración y ejecución de agente.
* Tool calls mínimas: nombre + status/success.
* Uso de lifecycle hooks oficiales de `openai-agents-sdk` 0.14+.
* Preparado para multiagente y configuraciones distintas de modelo por rol.
* Sin crear god-like files.

La base técnica recomendada son los `RunHooks` del SDK, porque `Runner.run(...)` acepta `hooks` oficialmente, y `RunHooksBase` expone `on_tool_start` / `on_tool_end` para observar tools locales. ([OpenAI GitHub][1])

---

# Plan de implementación: `feat/001/base-logging-refactor`

## Objetivo
refactorizar la observabilidad del proyecto:

```text
MongoDB / JSONL fallback
        ↓
SQLite local + artefactos por run + live.md
```

La implementación debe dejar `agent_flow.py` como orquestador, no como módulo de logging/persistencia. Ahora mismo `agent_flow.py` todavía acumula logs, tool calls, métricas, artifacts y persistencia final dentro del flujo principal, lo que es demasiado acoplamiento. 

---

# Principios de diseño

## 1. No sobreingeniería

Guardar solo lo útil para el TFM:

```text
Sí:
- duración total del run
- duración por iteración
- duración por ejecución de agente / Runner.run
- tokens por iteración/agente
- estado final
- stop_reason
- tests
- archivos modificados
- tool_name
- tool_status / success

No:
- duración por tool
- argumentos completos de tools
- resultados completos de tools
- stdout/stderr completos en SQLite
- chain-of-thought
- traces internas complejas del SDK
```

## 2. Separación clara de capas

```text
Capa interactiva:
- consola
- results/<run_id>/live.md

Capa analítica:
- results/observability.db

Artefactos:
- diff.patch
- changed_files.json
- patch_summary.json
- test outputs si aplica
```

## 3. Preparado para multiagente

Aunque ahora sea monoagente, el modelo debe soportar:

```text
architecture = mono_agent
agent_name = baseline
agent_role = fixer
model = llama3.1:8b
```

y más adelante:

```text
architecture = investigator_patcher_validator

agent_role = investigator
model = barato

agent_role = patcher
model = caro

agent_role = validator
model = barato
```

---

# Estructura de carpetas propuesta

Añadir un paquete nuevo:

```text
src/llm_autofix_agents/observability/
  __init__.py
  models.py
  observer.py
  sqlite_schema.py
  sqlite_store.py
  interactive.py
  lifecycle_hooks.py
  config.py
```

## Responsabilidades

```text
models.py
- Dataclasses/Pydantic models internos de observabilidad.

observer.py
- Protocolos e implementación Composite/Null.

sqlite_schema.py
- DDL SQLite y migración inicial.

sqlite_store.py
- Persistencia SQLite.

interactive.py
- Consola + live.md.

lifecycle_hooks.py
- RunHooks del openai-agents-sdk para tool calls.

config.py
- Resolución de configuración: results_dir, db_path, interactive.
```

No meter esta lógica en:

```text
agent_flow.py
tools/apr.py
llm/provider.py
```

---


# Fase 2 — Eliminar MongoDB (COMPLETADO)

MongoDB ha sido eliminado del proyecto.

## Task 2.1 — Eliminar dependencia `pymongo` (COMPLETADO)

`pyproject.toml` no incluye `pymongo` como dependencia.

## Task 2.2 — Eliminar persistencia MongoDB (COMPLETADO)

No hay código que persista en MongoDB. El módulo `flow/observability.py` no contiene referencias a MongoDB.

## Task 2.3 — Actualizar tests de observabilidad antiguos (COMPLETADO)

No hay tests MongoDB que eliminar.

Nuevo enfoque:

```text
- SQLite se crea correctamente.
- Inserta run.
- Inserta iteration.
- Inserta agent_execution.
- Inserta tool_call.
- Genera live.md.
```

---

# Fase 3 — Crear modelos de observabilidad

Crear:

```text
src/llm_autofix_agents/observability/models.py
```

## Task 3.1 — Definir modelos mínimos

Sugerencia:

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RunDescriptor:
    run_id: str
    architecture: str
    target_repo: str | None
    target_branch: str | None
    run_fingerprint: str
    prompt_hash: str | None = None
    experiment_id: str | None = None
    benchmark_name: str | None = None
    problem_id: str | None = None


@dataclass(frozen=True)
class ModelConfigDescriptor:
    provider: str
    model: str
    max_turns: int
    base_url: str | None = None
    tracing_disabled: bool = True


@dataclass(frozen=True)
class AgentDescriptor:
    agent_name: str
    agent_role: str
    model_config: ModelConfigDescriptor
    tool_profile: str
    agent_order: int = 1


@dataclass(frozen=True)
class IterationRecord:
    run_id: str
    iteration_id: str
    iteration_index: int
    started_at: str
    finished_at: str | None
    duration_seconds: float | None
    status: str | None
    stop_reason: str | None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tool_calls_count: int = 0
    changed_files_count: int = 0
    repo_changed: bool = False
    test_exit_code: int | None = None
    test_timed_out: bool | None = None
    test_signature: str | None = None


@dataclass(frozen=True)
class AgentExecutionRecord:
    agent_execution_id: str
    run_id: str
    iteration_id: str
    run_agent_id: str
    execution_index: int
    started_at: str
    finished_at: str | None
    duration_seconds: float | None
    status: str | None
    reasoning_summary: str | None
    confidence: float | None
    notes: str | None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    tool_calls_count: int = 0
    error_type: str | None = None
    error_message_short: str | None = None


@dataclass(frozen=True)
class ToolCallRecord:
    tool_call_id: str
    run_id: str
    iteration_id: str
    agent_execution_id: str | None
    seq: int
    tool_name: str
    status: str | None
    success: bool | None
```

Mantenerlo simple. No añadir argumentos/resultados.

---

# Fase 4 — Crear esquema SQLite

Crear:

```text
src/llm_autofix_agents/observability/sqlite_schema.py
```

## Task 4.1 — Definir schema versionado

Usar `PRAGMA user_version = 1`.

DDL recomendado:

```python
SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS architectures (
  architecture_id TEXT PRIMARY KEY,
  name TEXT NOT NULL UNIQUE,
  description TEXT
);

CREATE TABLE IF NOT EXISTS experiments (
  experiment_id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  description TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS model_configs (
  model_config_id TEXT PRIMARY KEY,
  provider TEXT NOT NULL,
  model TEXT NOT NULL,
  base_url TEXT,
  max_turns INTEGER,
  tracing_disabled INTEGER,
  extra_json TEXT,
  UNIQUE (
    provider,
    model,
    base_url,
    max_turns,
    tracing_disabled,
    extra_json
  )
);

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  experiment_id TEXT,
  architecture_id TEXT NOT NULL,

  started_at TEXT NOT NULL,
  finished_at TEXT,

  target_repo TEXT,
  target_branch TEXT,
  benchmark_name TEXT,
  problem_id TEXT,

  prompt_hash TEXT,
  run_fingerprint TEXT,

  final_status TEXT,
  stop_reason TEXT,
  resolved INTEGER NOT NULL DEFAULT 0,

  duration_seconds REAL,
  total_iterations INTEGER NOT NULL DEFAULT 0,

  total_input_tokens INTEGER NOT NULL DEFAULT 0,
  total_output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,

  files_changed_count INTEGER NOT NULL DEFAULT 0,

  live_log_path TEXT,
  summary_path TEXT,
  diff_path TEXT,

  FOREIGN KEY (experiment_id) REFERENCES experiments(experiment_id),
  FOREIGN KEY (architecture_id) REFERENCES architectures(architecture_id)
);

CREATE TABLE IF NOT EXISTS run_agents (
  run_agent_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,

  agent_name TEXT NOT NULL,
  agent_role TEXT NOT NULL,
  agent_order INTEGER,

  model_config_id TEXT NOT NULL,
  instructions_hash TEXT,
  tool_profile TEXT,

  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (model_config_id) REFERENCES model_configs(model_config_id),

  UNIQUE (run_id, agent_name)
);

CREATE TABLE IF NOT EXISTS iterations (
  iteration_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,

  iteration_index INTEGER NOT NULL,

  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_seconds REAL,

  status TEXT,
  stop_reason TEXT,

  repo_changed INTEGER NOT NULL DEFAULT 0,
  changed_files_count INTEGER NOT NULL DEFAULT 0,

  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,

  tool_calls_count INTEGER NOT NULL DEFAULT 0,

  test_exit_code INTEGER,
  test_timed_out INTEGER,
  test_signature TEXT,

  FOREIGN KEY (run_id) REFERENCES runs(run_id),

  UNIQUE (run_id, iteration_index)
);

CREATE TABLE IF NOT EXISTS agent_executions (
  agent_execution_id TEXT PRIMARY KEY,

  run_id TEXT NOT NULL,
  iteration_id TEXT NOT NULL,
  run_agent_id TEXT NOT NULL,

  execution_index INTEGER NOT NULL,

  started_at TEXT NOT NULL,
  finished_at TEXT,
  duration_seconds REAL,

  status TEXT,
  reasoning_summary TEXT,
  confidence REAL,
  notes TEXT,

  input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens INTEGER NOT NULL DEFAULT 0,
  total_tokens INTEGER NOT NULL DEFAULT 0,

  tool_calls_count INTEGER NOT NULL DEFAULT 0,

  error_type TEXT,
  error_message_short TEXT,

  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (run_agent_id) REFERENCES run_agents(run_agent_id)
);

CREATE TABLE IF NOT EXISTS tool_calls (
  tool_call_id TEXT PRIMARY KEY,

  run_id TEXT NOT NULL,
  iteration_id TEXT NOT NULL,
  agent_execution_id TEXT,

  seq INTEGER NOT NULL,

  tool_name TEXT NOT NULL,
  status TEXT,
  success INTEGER,

  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (agent_execution_id) REFERENCES agent_executions(agent_execution_id)
);

CREATE TABLE IF NOT EXISTS test_executions (
  test_execution_id TEXT PRIMARY KEY,

  run_id TEXT NOT NULL,
  iteration_id TEXT,
  agent_execution_id TEXT,
  tool_call_id TEXT,

  phase TEXT NOT NULL,

  command TEXT,
  duration_seconds REAL,

  exit_code INTEGER,
  timed_out INTEGER,

  tests_total INTEGER,
  tests_passed INTEGER,
  tests_failed INTEGER,

  output_path TEXT,
  signature TEXT,

  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (agent_execution_id) REFERENCES agent_executions(agent_execution_id),
  FOREIGN KEY (tool_call_id) REFERENCES tool_calls(tool_call_id)
);

CREATE TABLE IF NOT EXISTS file_changes (
  file_change_id TEXT PRIMARY KEY,

  run_id TEXT NOT NULL,
  iteration_id TEXT,
  agent_execution_id TEXT,
  tool_call_id TEXT,

  path TEXT NOT NULL,
  change_type TEXT,
  additions INTEGER,
  deletions INTEGER,

  detected_by TEXT,

  FOREIGN KEY (run_id) REFERENCES runs(run_id),
  FOREIGN KEY (iteration_id) REFERENCES iterations(iteration_id),
  FOREIGN KEY (agent_execution_id) REFERENCES agent_executions(agent_execution_id),
  FOREIGN KEY (tool_call_id) REFERENCES tool_calls(tool_call_id)
);
"""
```

## Task 4.2 — Añadir índices útiles

```sql
CREATE INDEX IF NOT EXISTS idx_runs_architecture ON runs(architecture_id);
CREATE INDEX IF NOT EXISTS idx_iterations_run ON iterations(run_id);
CREATE INDEX IF NOT EXISTS idx_agent_executions_run_agent ON agent_executions(run_agent_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_run ON tool_calls(run_id);
CREATE INDEX IF NOT EXISTS idx_tool_calls_name ON tool_calls(tool_name);
```

---

# Fase 5 — Implementar SQLiteStore

Crear:

```text
src/llm_autofix_agents/observability/sqlite_store.py
```

## Task 5.1 — Crear clase `SQLiteObservabilityStore`

Debe usar solo stdlib:

```python
import sqlite3
```

Métodos mínimos:

```python
class SQLiteObservabilityStore:
    def __init__(self, db_path: Path) -> None: ...

    def initialize(self) -> None: ...

    def upsert_architecture(self, name: str, description: str | None = None) -> str: ...

    def upsert_model_config(self, descriptor: ModelConfigDescriptor) -> str: ...

    def upsert_run_agent(...): ...

    def insert_run_started(...): ...

    def update_run_finished(...): ...

    def insert_iteration(...): ...

    def insert_agent_execution(...): ...

    def insert_tool_call(...): ...

    def insert_test_execution(...): ...

    def insert_file_change(...): ...
```

## Task 5.2 — IDs deterministas cuando tenga sentido

Usar hash estable para:

```text
architecture_id
model_config_id
run_agent_id
```

Ejemplo:

```python
def stable_id(prefix: str, payload: str) -> str:
    digest = sha256(payload.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}-{digest}"
```

Para registros concretos:

```text
tool_call_id
agent_execution_id
test_execution_id
file_change_id
```

pueden ser deterministas por composición:

```text
{run_id}-it01-agent01
{run_id}-it01-tool003
```

---

# Fase 6 — Implementar configuración de observabilidad

Crear:

```text
src/llm_autofix_agents/observability/config.py
```

## Task 6.1 — Definir config

```python
@dataclass(frozen=True)
class ObservabilityConfig:
    enabled: bool
    interactive: bool
    results_dir: Path
    sqlite_db_path: Path
    live_log_enabled: bool
```

## Task 6.2 — Resolver desde env + metadata

Prioridad:

```text
RunInput.metadata > environment > defaults
```

Defaults:

```text
enabled = true
interactive = false
results_dir = <repo_root>/results
sqlite_db_path = <repo_root>/results/observability.db
live_log_enabled = true
```

Variables opcionales:

```text
AUTOFIX_OBSERVABILITY_ENABLED=true|false
AUTOFIX_INTERACTIVE=true|false
AUTOFIX_RESULTS_DIR=results
AUTOFIX_OBSERVABILITY_DB=results/observability.db
AUTOFIX_LIVE_LOG=true|false
```

---

# Fase 7 — Implementar Observer

Crear:

```text
src/llm_autofix_agents/observability/observer.py
```

## Task 7.1 — Definir protocolo

```python
class RunObserver(Protocol):
    def on_run_started(...) -> None: ...
    def on_run_finished(...) -> None: ...
    def on_iteration_started(...) -> None: ...
    def on_iteration_finished(...) -> None: ...
    def on_agent_execution_started(...) -> None: ...
    def on_agent_execution_finished(...) -> None: ...
    def on_tool_call(...) -> None: ...
    def on_test_execution(...) -> None: ...
    def on_file_change(...) -> None: ...
```

No usar async aquí si no hace falta. Los lifecycle hooks son async, pero pueden llamar a métodos síncronos simples.

## Task 7.2 — Implementar `NullObserver`

Para tests o observabilidad desactivada.

## Task 7.3 — Implementar `CompositeObserver`

```python
class CompositeObserver:
    def __init__(self, observers: Sequence[RunObserver]) -> None:
        self._observers = list(observers)
```

Debe intentar llamar a todos. Si un observer falla, no debería romper el run APR. Registrar con `logging.warning`.

## Task 7.4 — Implementar `SQLiteObserver`

Puede vivir en `sqlite_store.py` o `observer.py`, pero mejor separado:

```text
sqlite_store.py -> DB
observer.py -> interfaz
```

---

# Fase 8 — Implementar capa interactiva

Crear:

```text
src/llm_autofix_agents/observability/interactive.py
```

## Task 8.1 — `MarkdownLiveObserver`

Escribe en:

```text
results/<run_id>/live.md
```

Debe registrar:

```md
# Run <run_id>

- Architecture: mono_agent
- Agent: baseline / fixer
- Started at: ...

## Iteration 1

### Agent execution: baseline

Reasoning summary:
...

Tool calls:
- read_file: success
- search_files: success
- replace_lines: success
- run_test_target: failed

Iteration result:
- status: in_progress
- tests: exit_code=1
```

## Task 8.2 — `ConsoleObserver`

Solo si `interactive=true`.

Formato simple:

```text
[run] started run-...
[it 1] started
[agent baseline/fixer] Runner.run started
[tool] read_file -> success
[tool] run_test_target -> failed
[it 1] finished status=in_progress tokens=...
[run] finished status=success stop_reason=completed
```

No imprimir JSON completo ni outputs gigantes.

---

# Fase 9 — Implementar lifecycle hooks del SDK

Crear:

```text
src/llm_autofix_agents/observability/lifecycle_hooks.py
```

La documentación oficial indica que `RunHooksBase.on_tool_start` se llama inmediatamente antes de una tool local, y `on_tool_end` inmediatamente después, recibiendo el `result: str`. ([OpenAI GitHub][1])

## Task 9.1 — Crear `APRRunHooks`

```python
from agents import RunHooksBase, RunContextWrapper, Tool

class APRRunHooks(RunHooksBase[APRToolContext, Agent[Any]]):
    def __init__(
        self,
        *,
        observer: RunObserver,
        run_id: str,
        iteration_id: str,
        agent_execution_id: str,
    ) -> None:
        ...
```

## Task 9.2 — Registrar secuencia de tools

Dentro del hook:

```python
self._seq += 1
```

Guardar `tool_name` + status.

## Task 9.3 — Inferir status desde result

Tus APR tools suelen devolver JSON con `"ok": true/false`. 

Función:

```python
def infer_tool_status(result: str) -> tuple[str, bool | None]:
    try:
        payload = json.loads(result)
    except json.JSONDecodeError:
        return "unknown", None

    ok = payload.get("ok")
    if ok is True:
        return "success", True
    if ok is False:
        return "failed", False
    return "unknown", None
```

## Task 9.4 — Implementar `on_tool_end`

```python
async def on_tool_end(self, context, agent, tool, result: str) -> None:
    tool_name = getattr(tool, "name", None) or tool.__class__.__name__
    status, success = infer_tool_status(result)
    self._observer.on_tool_call(
        ToolCallRecord(
            tool_call_id=f"{self._agent_execution_id}-tool{self._seq:03d}",
            run_id=self._run_id,
            iteration_id=self._iteration_id,
            agent_execution_id=self._agent_execution_id,
            seq=self._seq,
            tool_name=tool_name,
            status=status,
            success=success,
        )
    )
```

## Task 9.5 — No registrar duración por tool

No usar `time.perf_counter()` dentro de hooks de tool.

---

# Fase 10 — Modificar provider para aceptar hooks

Editar:

```text
src/llm_autofix_agents/llm/provider.py
```

Ahora `OpenAIAgentsSDKProvider.run_prompt(...)` llama a `Runner.run(...)`. 

## Task 10.1 — Actualizar protocolo `LLMProvider`

Añadir parámetro opcional:

```python
hooks: RunHooks[Any] | None = None
```

Firma:

```python
async def run_prompt(
    self,
    *,
    instructions: str,
    user_input: str,
    max_turns: int,
    tools: Sequence[object] | None = None,
    context: Any | None = None,
    hooks: RunHooks[Any] | None = None,
) -> AgentFixIterationRecord:
```

## Task 10.2 — Pasar hooks a `Runner.run`

```python
result = await Runner.run(
    self._build_agent(...),
    user_input,
    context=context,
    max_turns=max_turns,
    hooks=hooks,
    run_config=RunConfig(tracing_disabled=self.settings.tracing_disabled),
)
```

`Runner.run` soporta oficialmente `hooks`. ([OpenAI GitHub][2])

## Task 10.3 — Mantener extracción de tokens

No cambiar:

```python
usage = _extract_token_usage(result)
```

## Task 10.4 — Reducir dependencia de `_extract_tool_calls`

Puedes conservarlo como fallback en `proposal.tool_calls`, pero la fuente analítica principal debe ser `APRRunHooks`.

Opciones:

```text
A. Mantener proposal.tool_calls para compatibilidad.
B. Dejar de usarlo en agent_flow para persistencia.
```

Recomendado: B.

---

# Fase 11 — Refactorizar `agent_flow.py`

Editar:

```text
src/llm_autofix_agents/agent_flow.py
```

Este es el cambio más delicado.

## Task 11.1 — Añadir construcción de observer

Al inicio de `run_agent_baseline`:

```python
observability_config = resolve_observability_config(...)
observer = build_observer(...)
```

## Task 11.2 — Registrar `run_started`

Después de resolver:

```text
repo_root
settings
tool_profile
agent_config
```

emitir:

```python
observer.on_run_started(...)
```

## Task 11.3 — Crear `run_agent` para monoagente

Por ahora:

```text
agent_name = baseline
agent_role = fixer
agent_order = 1
```

El modelo viene de `LLMSettings`:

```text
provider
model
base_url
max_turns
tracing_disabled
```

## Task 11.4 — Medir tiempo total del run

Mantener:

```python
run_started_monotonic = time.perf_counter()
```

Al final:

```python
duration_seconds = time.perf_counter() - run_started_monotonic
```

## Task 11.5 — Medir tiempo por iteración

Dentro del loop:

```python
iteration_started_monotonic = time.perf_counter()
iteration_started_at = utc_now_iso()
```

Al cerrar la iteración:

```python
iteration_duration_seconds = time.perf_counter() - iteration_started_monotonic
```

## Task 11.6 — Medir tiempo de ejecución de agente / Runner.run

Alrededor de:

```python
resolved_provider.run_prompt(...)
```

hacer:

```python
agent_execution_started = time.perf_counter()
proposal = _run_sync(...)
agent_execution_duration = time.perf_counter() - agent_execution_started
```

Esto mide `Runner.run`, no cada tool.

## Task 11.7 — Crear hooks por ejecución de agente

Antes de llamar al provider:

```python
hooks = APRRunHooks(
    observer=observer,
    run_id=identity.run_id,
    iteration_id=identity.iteration_id,
    agent_execution_id=agent_execution_id,
)
```

Pasar:

```python
hooks=hooks
```

a `run_prompt`.

## Task 11.8 — Eliminar acumulación analítica de tool calls

Actualmente:

```python
accumulated_tool_calls.extend(...)
```

No debe alimentar SQLite.

Puede mantenerse solo si `RunOutput.artifacts["observability"]` todavía lo necesita temporalmente, pero el objetivo es retirarlo progresivamente.

## Task 11.9 — Reducir `accumulated_logs`

`RunOutput.logs` debe quedar como compatibilidad mínima:

```text
run_id=...
status=...
stop_reason=...
duration_seconds=...
observability_backend=sqlite
observability_db=results/observability.db
live_log=results/<run_id>/live.md
```

No usarlo como fuente principal de eventos.

## Task 11.10 — Registrar `iteration_finished`

Después de tests y validaciones:

```python
observer.on_iteration_finished(...)
```

Incluir:

```text
status
stop_reason si aplica
tokens
tool_calls_count
changed_files_count
test_exit_code
test_signature
duration_seconds
```

## Task 11.11 — Registrar `agent_execution_finished`

Después de obtener `proposal`:

```python
observer.on_agent_execution_finished(...)
```

Incluir:

```text
status = proposal.status
reasoning_summary
confidence
notes
tokens
tool_calls_count = hooks.tool_call_count
duration_seconds
```

## Task 11.12 — Registrar `run_finished`

En cada return path, antes de devolver `RunOutput`.

Evitar duplicar lógica: crear helper interno:

```python
def _finish_run(...)
```

o una clase pequeña de runtime state para evitar repetir mucho.

---

# Fase 12 — Reemplazar `_finalize_run_output`

Actualmente `_finalize_run_output` calcula métricas, construye observability record y persiste. 

## Task 12.1 — Convertir `_finalize_run_output`

Nueva responsabilidad:

```text
- completar artifacts mínimos
- llamar observer.on_run_finished
- devolver RunOutput
```

No debe:

```text
- persistir MongoDB
- persistir JSONL como backend principal
- construir RunObservabilityRecord monolítico
```

## Task 12.2 — Mantener `summary.json`

Generar:

```text
results/<run_id>/summary.json
```

Con:

```json
{
  "run_id": "...",
  "status": "...",
  "stop_reason": "...",
  "duration_seconds": 123.4,
  "iterations": 2,
  "tokens": {
    "input": 1000,
    "output": 500,
    "total": 1500
  },
  "changed_files_count": 1,
  "observability_db": "results/observability.db",
  "live_log": "results/<run_id>/live.md"
}
```

Puede vivir en `interactive.py` o nuevo módulo `summary.py`. Si se añade, usar:

```text
observability/summary.py
```

---

# Fase 13 — Integrar test executions

## Task 13.1 — Registrar baseline test

Cuando `baseline_test_execution` exista:

```python
observer.on_test_execution(
    phase="baseline",
    command=run_input.test_command,
    exit_code=...,
    timed_out=...,
    signature=...,
)
```

## Task 13.2 — Registrar validación por iteración

Después de `_run_test_command` dentro del loop:

```python
phase="iteration_validation"
```

No hace falta capturar duración si `TestExecution` no la tiene todavía. Si no existe, dejar `duration_seconds=None`.

---

# Fase 14 — Integrar file changes

Ya existe persistencia de artifacts por iteración con `file_changes.json` y `patch_summary.json`. 

## Task 14.1 — No duplicar parsing complejo

Usar lo que ya produce:

```python
_persist_iteration_artifacts(...)
```

y/o `changed_files`.

## Task 14.2 — Insertar cambios mínimos

Por cada `changed_file`:

```text
path
change_type = unknown/modified
detected_by = snapshot_diff
```

Si luego quieres additions/deletions, ya están en artifacts. No meter más complejidad ahora.

---

# Fase 15 — Actualizar CLI

Editar:

```text
src/llm_autofix_agents/main.py
```

Ahora `agent-smoke` imprime el `RunOutput` completo al final. 

## Task 15.1 — Añadir flags opcionales a `agent-smoke`

```text
--interactive
--observability-db
--results-dir
```

Ejemplo:

```python
agent_parser.add_argument("--interactive", action="store_true")
agent_parser.add_argument("--observability-db")
agent_parser.add_argument("--results-dir")
```

## Task 15.2 — Pasar flags vía metadata

```python
metadata["interactive"] = args.interactive
metadata["observability_db"] = args.observability_db
metadata["results_dir"] = args.results_dir
```

## Task 15.3 — Mantener compatibilidad env

También leer:

```text
AUTOFIX_INTERACTIVE
AUTOFIX_OBSERVABILITY_DB
AUTOFIX_RESULTS_DIR
```

desde `observability/config.py`.

---

# Fase 16 — Actualizar contracts

Editar:

```text
src/llm_autofix_agents/contracts.py
```

Ahora tiene `RunObservabilityRecord`, `RunMetrics`, `ToolCallTrace`, etc. 

## Task 16.1 — Decidir si mantener compatibilidad

Recomendación:

* Mantener `RunOutput`.
* Mantener `RunMetrics` si no molesta.
* Marcar `RunObservabilityRecord` como legacy o dejar de usarlo.
* No añadir más modelos de observabilidad a `contracts.py`.

## Task 16.2 — Reducir dependencia del contrato antiguo

`agent_flow.py` debería dejar de importar:

```python
build_observability_record
persist_observability_record
```

desde `flow`.

---

# Fase 17 — Actualizar `flow/__init__.py`

Editar:

```text
src/llm_autofix_agents/flow/__init__.py
```

Actualmente reexporta:

```python
build_observability_record
build_run_metrics
persist_observability_record
```



## Task 17.1 — Retirar reexports si ya no se usan

Eliminar:

```python
from llm_autofix_agents.flow.observability import (...)
```

o mantener temporalmente si tests legacy lo necesitan, pero idealmente retirarlo.

---

# Fase 18 — Tests nuevos

## Task 18.1 — `tests/test_sqlite_observability.py`

Casos:

```text
- crea DB
- crea schema
- upsert architecture
- upsert model config
- insert run
- insert run_agent
- insert iteration
- insert agent_execution
- insert tool_call
- lee datos con SELECT y verifica campos
```

## Task 18.2 — `tests/test_lifecycle_hooks.py`

Casos:

```text
- infer_tool_status({"ok": true}) -> success, True
- infer_tool_status({"ok": false}) -> failed, False
- infer_tool_status("not-json") -> unknown, None
- on_tool_end registra tool_call con nombre/status
```

No hace falta ejecutar `Runner.run` real. Se pueden usar fakes.

## Task 18.3 — `tests/test_interactive_observer.py`

Casos:

```text
- crea live.md
- escribe run started
- escribe iteration started
- escribe tool call
- escribe run finished
```

## Task 18.4 — Actualizar `tests/test_agent_flow.py`

Actualmente espera logs tipo:

```text
stage=observability
observability_backend=jsonl
```



Cambiar a:

```text
observability_backend=sqlite
observability_db=...
live_log=...
```

o verificar `output.artifacts`.

## Task 18.5 — Actualizar `tests/test_llm_provider.py`

Este test parece estar desalineado con el schema actual porque usa `action`/`rationale`, mientras el provider actual usa `status`/`reasoning_summary`.  

Cambiar:

```text
action -> status
rationale -> reasoning_summary
finish -> done
continue -> in_progress
```

## Task 18.6 — Eliminar tests MongoDB

Eliminar casos de:

```text
MONGODB_CONNECTION_URL
fallback_reason
_persist_to_mongodb
```

---

# Fase 19 — Actualizar spec

Editar:

```text
specs/001-mono-agente-entorno/spec.md
```

Ahora I42 dice MongoDB Atlas + fallback JSONL, y los criterios de aceptación también exigen MongoDB. 

## Task 19.1 — Cambiar decisión I42

De:

```text
I42: Persistencia inicial de resultados = MongoDB Atlas como primario + fallback JSONL local.
```

A:

```text
I42: Persistencia inicial de resultados = SQLite local normalizado para ETL + artefactos locales por run.
```

## Task 19.2 — Cambiar I43

De:

```text
I43: Logging = INFO por defecto y DEBUG activable.
```

A:

```text
I43: Observabilidad separada en capa interactiva y capa analítica:
- interactiva: consola/live.md para seguimiento humano;
- analítica: SQLite local para ETL.
```

## Task 19.3 — Cambiar E24

De:

```text
E24: Trazabilidad completa de tool calls.
```

A:

```text
E24: Trazabilidad mínima de tool calls mediante lifecycle hooks oficiales del SDK:
tool_name, status/success, iteración y agente.
```

## Task 19.4 — Cambiar criterios de aceptación

Eliminar:

```text
Se registran resultados en MongoDB Atlas con fallback JSONL local...
```

Añadir:

```text
Se registran resultados en SQLite local con esquema normalizado para runs, arquitecturas, agentes, modelos, iteraciones, ejecuciones de agente, tests, cambios de archivo y tool calls mínimas.
```

Añadir:

```text
La capa interactiva genera un live.md por run sin mezclarse con la capa analítica.
```

---

# Fase 20 — Actualizar tasks

Editar:

```text
specs/001-mono-agente-entorno/tasks.md
```

Ahora SH5 todavía habla de MongoDB. 

## Task 20.1 — Reabrir/reformular SH5

Cambiar:

```text
SH5 - Observabilidad y datos experimentales
```

a:

```text
SH5 - Observabilidad SQLite-first y logging estructurado
```

## Task 20.2 — Reemplazar tasks SH5

Sugerencia:

```md
## SH5 - Observabilidad SQLite-first y logging estructurado (En curso)

### Objetivo
Separar la observabilidad interactiva de la analítica, eliminar MongoDB del MVP y persistir datos experimentales en SQLite local.

### Tasks
- [ ] SH5-T01 Eliminar MongoDB/pymongo del runtime principal.
- [ ] SH5-T02 Definir esquema SQLite normalizado para runs, architectures, model_configs, run_agents, iterations, agent_executions, tool_calls, test_executions y file_changes.
- [ ] SH5-T03 Implementar SQLiteObservabilityStore con migración inicial.
- [ ] SH5-T04 Implementar observers desacoplados: Null, Composite, SQLite y Markdown/Console.
- [ ] SH5-T05 Integrar lifecycle hooks oficiales del openai-agents-sdk para registrar tool calls mínimas.
- [ ] SH5-T06 Refactorizar agent_flow para emitir eventos y dejar de persistir observabilidad directamente.
- [ ] SH5-T07 Generar live.md y summary.json por run.
- [ ] SH5-T08 Actualizar tests y retirar cobertura MongoDB.
- [ ] SH5-T09 Actualizar README/status/spec con la decisión SQLite-first.

### Done cuando
- Una ejecución genera observability.db, live.md y summary.json.
- SQLite permite consultar runs, iteraciones, agentes, modelos, tests, cambios y tool calls mínimas.
- agent_flow no contiene lógica de backend de persistencia.
- MongoDB no forma parte del core del proyecto.
```

---

# Fase 21 — Actualizar status

Editar:

```text
specs/status.md
```

El status actual dice que SH5 está completado con MongoDB Atlas y fallback JSONL. 

## Task 21.1 — Añadir entrada en “Hecho”

```md
- Decisión de observabilidad revisada: MongoDB deja de ser backend principal del MVP; se adopta SQLite local normalizado + artefactos por run para facilitar ETL y reducir complejidad operativa.
```

## Task 21.2 — Actualizar “En curso”

```md
- Subhito activo: refactor de observabilidad SQLite-first y logging estructurado.
- Task activa: separar capa interactiva y analítica, integrar hooks oficiales del SDK y desacoplar agent_flow.
```

## Task 21.3 — Actualizar “Siguiente”

```md
- Validar observability.db con una ejecución QuixBugs MVP y preparar queries básicas para análisis experimental.
```

---

# Fase 22 — Actualizar README

Editar:

```text
README.md
```

Ya documenta APR tools y QuixBugs. 

## Task 22.1 — Añadir sección “Observabilidad”

Ejemplo:

```md
## Observabilidad local

Cada ejecución genera:

- `results/observability.db`: base SQLite para análisis/ETL.
- `results/<run_id>/live.md`: log interactivo legible.
- `results/<run_id>/summary.json`: resumen final del run.
- `results/<run_id>/itXX/`: artefactos por iteración.

La base SQLite registra:
- runs
- architectures
- model_configs
- run_agents
- iterations
- agent_executions
- tool_calls
- test_executions
- file_changes

Las tool calls se registran de forma mínima:
- nombre
- status/success
- iteración
- agente
```

## Task 22.2 — Documentar env vars

```md
### Variables de observabilidad

- `AUTOFIX_OBSERVABILITY_ENABLED=true|false`
- `AUTOFIX_INTERACTIVE=true|false`
- `AUTOFIX_RESULTS_DIR=results`
- `AUTOFIX_OBSERVABILITY_DB=results/observability.db`
- `AUTOFIX_LIVE_LOG=true|false`
```

---

# Fase 23 — Validación

## Task 23.1 — Formato

```bash
make format
```

## Task 23.2 — Tests

```bash
make test
```

## Task 23.3 — Smoke local

```bash
uv run autofix agent-smoke --interactive
```

## Task 23.4 — Smoke Compose

```bash
make compose-up
make compose-smoke
make compose-down
```

El Makefile ya tiene targets para format, test y compose smoke. 

---

# Orden recomendado de commits

Para que la PR sea revisable:

## Commit 1

```text
chore: remove mongodb dependency
```

Incluye:

```text
pyproject.toml
tests eliminados/ajustados mínimamente
```

## Commit 2

```text
feat: add sqlite observability store
```

Incluye:

```text
observability/models.py
observability/sqlite_schema.py
observability/sqlite_store.py
tests/test_sqlite_observability.py
```

## Commit 3

```text
feat: add interactive observability observers
```

Incluye:

```text
observability/observer.py
observability/interactive.py
observability/config.py
tests/test_interactive_observer.py
```

## Commit 4

```text
feat: record apr tool calls via sdk lifecycle hooks
```

Incluye:

```text
observability/lifecycle_hooks.py
provider.py hooks parameter
tests/test_lifecycle_hooks.py
tests/test_llm_provider.py
```

## Commit 5

```text
refactor: decouple observability from agent flow
```

Incluye:

```text
agent_flow.py
contracts.py si aplica
flow/__init__.py
tests/test_agent_flow.py
```

## Commit 6

```text
docs: update sqlite-first observability spec
```

Incluye:

```text
spec.md
tasks.md
status.md
README.md
```

---

# Queries de validación para ETL

Cuando esté implementado, probar:

```sql
SELECT COUNT(*) FROM runs;
SELECT COUNT(*) FROM iterations;
SELECT COUNT(*) FROM agent_executions;
SELECT COUNT(*) FROM tool_calls;
```

Tools más usadas:

```sql
SELECT
  tool_name,
  COUNT(*) AS calls,
  AVG(success) AS success_rate
FROM tool_calls
GROUP BY tool_name
ORDER BY calls DESC;
```

Tiempo medio por arquitectura:

```sql
SELECT
  a.name AS architecture,
  AVG(r.duration_seconds) AS avg_run_seconds,
  AVG(i.duration_seconds) AS avg_iteration_seconds,
  AVG(r.total_tokens) AS avg_tokens
FROM runs r
JOIN architectures a ON a.architecture_id = r.architecture_id
JOIN iterations i ON i.run_id = r.run_id
GROUP BY a.name;
```

Tokens por rol/modelo:

```sql
SELECT
  ra.agent_role,
  mc.provider,
  mc.model,
  AVG(ae.total_tokens) AS avg_tokens,
  AVG(ae.duration_seconds) AS avg_seconds
FROM agent_executions ae
JOIN run_agents ra ON ra.run_agent_id = ae.run_agent_id
JOIN model_configs mc ON mc.model_config_id = ra.model_config_id
GROUP BY ra.agent_role, mc.provider, mc.model;
```

---

# Criterios de aceptación de la PR

La PR se considera completa cuando:

```text
[ ] MongoDB y pymongo desaparecen del core.
[ ] results/observability.db se crea automáticamente.
[ ] results/<run_id>/live.md se crea cuando live log está habilitado.
[ ] results/<run_id>/summary.json se genera al final.
[ ] agent_flow.py no persiste directamente MongoDB/JSONL.
[ ] provider.py acepta hooks y los pasa a Runner.run.
[ ] lifecycle hooks registran tool_name + status/success.
[ ] No se mide duración por tool.
[ ] Se mide duración por run.
[ ] Se mide duración por iteración.
[ ] Se mide duración por ejecución de agente.
[ ] SQLite soporta monoagente y futuro multiagente.
[ ] Tests unitarios actualizados.
[ ] SPEC/status/tasks/README actualizados.
[ ] make format pasa.
[ ] make test pasa.
```

---

# Nota final para el agente de código

La implementación debe priorizar **simplicidad y bajo acoplamiento**.

No debe convertir:

```text
agent_flow.py
tools/apr.py
provider.py
sqlite_store.py
```

en archivos gigantes.

La dependencia principal de observabilidad con el SDK debe ser esta:

```text
Runner.run(..., hooks=APRRunHooks(...))
```

porque es el mecanismo oficial de lifecycle events del SDK para observar tool calls locales. ([OpenAI GitHub][1])

[1]: https://openai.github.io/openai-agents-python/ref/lifecycle/?utm_source=chatgpt.com "Lifecycle - OpenAI Agents SDK"
[2]: https://openai.github.io/openai-agents-python/ref/run/?utm_source=chatgpt.com "Runner - OpenAI Agents SDK"
