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

Nota sobre recursos del runner Docker (MVP):

- Por defecto solo se aplica timeout de ejecucion.
- No se aplican flags extra de hardening/aislamiento en `docker run` para reducir complejidad inicial.
- Limites de CPU/RAM/PIDs quedan como configuracion opcional para fases posteriores.

### MCP servers used by baseline agent

The baseline run uses MCP stdio servers for filesystem, shell command execution, and web search.

Default server commands:

- Filesystem MCP: `npx -y @modelcontextprotocol/server-filesystem <target_repo>`
- Shell MCP: `npx -y mcp-shell-server`
- Web search MCP: `npx -y web-search-mcp`

Optional environment overrides:

- `FILESYSTEM_MCP_ENABLED=true|false`
- `FILESYSTEM_MCP_COMMAND=<command>`
- `FILESYSTEM_MCP_ARGS_JSON=["..."]`
- `SHELL_MCP_ENABLED=true|false` (default: true)
- `SHELL_MCP_COMMAND=<command>`
- `SHELL_MCP_ARGS_JSON=["..."]`
- `SHELL_MCP_PACKAGE=<npm-package>`
- `SHELL_MCP_ENV_JSON={"KEY":"VALUE"}`
- `WEB_SEARCH_MCP_ENABLED=true|false` (default: true)
- `WEB_SEARCH_MCP_COMMAND=<command>`
- `WEB_SEARCH_MCP_ARGS_JSON=["..."]`
- `WEB_SEARCH_MCP_ENTRYPOINT=<path-to-dist-index.js>`
- `WEB_SEARCH_MCP_ENV_JSON={"KEY":"VALUE"}`

4. Format and run tests:

	make format
	make test