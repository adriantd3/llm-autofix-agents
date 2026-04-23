# llm-autofix-agents

# Target datasets to test:
- QuixBugs: https://github.com/jkoppel/QuixBugs
- SWE-Bench (Lite): https://github.com/swe-bench/SWE-bench

## Make targets minimos

Comandos imprescindibles para esta fase:

- `make format`
- `make test`
- `make run`
- `make compose-up`
- `make compose-smoke`
- `make compose-down`

## Bootstrap rapido

Regla de gestion de dependencias del proyecto:

- Todas las instalaciones o altas de dependencias deben hacerse con `uv add`.

1. Synchronize dependencies:

	uv sync

2. Run baseline in local host mode:

	make run

3. Run baseline in Compose runtime mode:

	make compose-up
	make compose-smoke
	make compose-down

Baseline recomendado para MVP (gratis/local):

- `LLM_PROVIDER=ollama`
- `OLLAMA_BASE_URL=http://localhost:11434/v1`
- `LLM_MODEL=llama3.1:8b`

Compatibilidad opcional:

- OpenAI: `LLM_PROVIDER=openai` + `OPENAI_API_KEY`
- Gemini: `LLM_PROVIDER=gemini` + `GEMINI_API_KEY`

## Runtime Completo Contenedizado (Compose Local)

Para ejecutar el runtime completo dentro de un contenedor local:

1. Levantar el runner:

	make compose-up

2. Ejecutar smoke:

	make compose-smoke

3. Apagar el entorno:

	make compose-down

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

## QuixBugs: run MVP listo

Configuracion recomendada para un primer gate reproducible (caso unico):

- `RUN_REPOSITORY=https://github.com/jkoppel/QuixBugs.git`
- `RUN_BRANCH=master`
- `RUN_TEST_COMMAND=uv run --with pytest pytest python_testcases/test_gcd.py`

Comando con Compose:

```bash
make compose-up
make compose-smoke
make compose-down
```

Comando local equivalente (sin Compose):

```bash
RUN_REPOSITORY=https://github.com/jkoppel/QuixBugs.git \
RUN_BRANCH=master \
RUN_ARCHITECTURE=mono-agent \
RUN_AGENT_MODELS='{"main":"llama3.1:8b"}' \
RUN_BOOTSTRAP_PROMPT='Fix failing tests with minimal changes.' \
RUN_TEST_COMMAND='uv run --with pytest pytest python_testcases/test_gcd.py' \
uv run autofix agent-smoke
```