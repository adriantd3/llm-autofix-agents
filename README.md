# llm-autofix-agents

# Target datasets to test:
- QuixBugs: https://github.com/jkoppel/QuixBugs
- SWE-Bench (Lite): https://github.com/swe-bench/SWE-bench

## Make targets minimos

Comandos imprescindibles para esta fase:

- `make format`
- `make test`
- `make docker-run`
- `make quixbugs-gcd-run`
- `make docker-debug-shell` (solo debug)

## Bootstrap rapido

Regla de gestion de dependencias del proyecto:

- Todas las instalaciones o altas de dependencias deben hacerse con `uv add`.

1. Synchronize dependencies:

	uv sync

2. Run baseline in Compose runtime mode (efimero):

	make docker-run

Baseline recomendado para MVP en Docker Compose:

Configura estas variables en un archivo `.env` (puedes partir de `.env.example`):

- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://host.docker.internal:11500/v1`
- `LLM_MODEL=llama3.1:8b`

Compatibilidad opcional:

- OpenAI: `LLM_PROVIDER=openai` + `OPENAI_API_KEY`
- Gemini: `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`

## Runtime Completo Contenedizado (Docker Compose)

Para ejecutar el runtime completo con Docker Compose:

1. Ejecutar un run efimero (crea contenedor, ejecuta `autofix run`, termina y elimina contenedor):

	make docker-run

2. Debug opcional en shell interactiva:

	make docker-debug-shell

Contrato minimo de instanciacion por contenedor (SH3-T02C):

- `RUN_REPOSITORY`
- `RUN_BRANCH`
- `RUN_ARCHITECTURE`
- `RUN_AGENT_MODELS`
- `RUN_BOOTSTRAP_PROMPT`
- `RUN_TEST_COMMAND` (opcional, recomendado para validacion objetiva)

`RUN_REPOSITORY` acepta:

- Ruta local existente.
- URL git remota (`https://...`, `git@...`).
- Slug de GitHub (`owner/repo`), que se resuelve a `https://github.com/owner/repo.git`.

Si el repo no existe localmente, el runtime lo clona de forma temporal antes del run.

Nota sobre recursos del runner Docker (MVP):

- Por defecto solo se aplica timeout de ejecucion.
- No se aplican flags extra de hardening/aislamiento en `docker run` para reducir complejidad inicial.
- Limites de CPU/RAM/PIDs quedan como configuracion opcional para fases posteriores.

### Local APR tools used by the baseline agent

The baseline run uses local APR tools from `src/llm_autofix_agents/tools/`. The default profile is `full`, which includes filesystem inspection, command execution, validation helpers, and git/diff helpers.

Available profiles:

- `minimal`: read/search/edit plus command execution.
- `core`: workspace inspection plus search, editing, command execution, and targeted test running.
- `full`: `core` plus git status/diff and unified diff application.

The active profile is resolved by the runtime and can be overridden through run metadata when needed.

4. Format and run tests:

	make format
	make test

## QuixBugs: prueba real minima gcd

Esta seccion describe una ejecucion real minima end-to-end sobre QuixBugs `gcd`.
No es un benchmark runner completo ni una ejecucion batch multi-caso.

Configuracion recomendada para esta prueba real minima en Docker Compose:

- `RUN_REPOSITORY=https://github.com/jkoppel/QuixBugs.git`
- `RUN_BRANCH=master`
- `RUN_TEST_COMMAND=uv run --with pytest pytest python_testcases/test_gcd.py`

Ejecucion real con Compose (efimera):

```bash
make docker-run
```

Atajo para `gcd`:

```bash
make quixbugs-gcd-run
```

Se usa `timeout 180s` al inicio para detectar bloqueos tempranos.
Si el flujo arranca bien pero el LLM necesita mas tiempo, subir a `timeout 600s` o mas.

Al terminar, revisar:

- `results/<run_id>/summary.json`
- `results/<run_id>/live.md`
- `results/observability.db`
- status final del run
- diff aplicado
- test final
- errores/tool calls si falla

## Observabilidad local

Cada ejecucion genera:

- `results/observability.db`: base SQLite para analisis/ETL.
- `results/<run_id>/live.md`: log interactivo legible.
- `results/<run_id>/summary.json`: resumen final del run.
- `results/<run_id>/itXX/`: artefactos por iteracion (diff.patch, patch_summary.json, file_changes.json).

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

Las tool calls se registran de forma minima:
- nombre
- status/success
- iteracion
- agente

### Variables de observabilidad

- `AUTOFIX_OBSERVABILITY_ENABLED=true|false` (default: true)
- `AUTOFIX_INTERACTIVE=true|false` (default: false)
- `AUTOFIX_RESULTS_DIR=results` (default: results)
- `AUTOFIX_OBSERVABILITY_DB=results/observability.db` (default: results/observability.db)
- `AUTOFIX_LIVE_LOG=true|false` (default: true)