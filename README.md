# llm-autofix-agents

## SH1 Docker runner bootstrap

1. Synchronize dependencies:

	uv sync

2. Build the runner image:

	make docker-build

3. Execute a smoke command in an ephemeral container:

	make docker-smoke

4. Validate run contracts (input/output/error models):

	make contracts-smoke

5. Run baseline agent smoke (defaults to Ollama):

	make agent-smoke

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

2. Ver estado de servicios:

	make compose-ps

3. Ejecutar smoke:

	make compose-smoke

4. Apagar el entorno:

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

The baseline run uses MCP stdio servers for filesystem and web search.

Default server commands:

- Filesystem MCP: `npx -y @modelcontextprotocol/server-filesystem <target_repo>`
- Web search MCP: `npx -y web-search-mcp`

Optional environment overrides:

- `FILESYSTEM_MCP_ENABLED=true|false`
- `FILESYSTEM_MCP_COMMAND=<command>`
- `FILESYSTEM_MCP_ARGS_JSON=["..."]`
- `WEB_SEARCH_MCP_ENABLED=true|false`
- `WEB_SEARCH_MCP_COMMAND=<command>`
- `WEB_SEARCH_MCP_ARGS_JSON=["..."]`
- `WEB_SEARCH_MCP_ENTRYPOINT=<path-to-dist-index.js>`
- `WEB_SEARCH_MCP_ENV_JSON={"KEY":"VALUE"}`

6. Run full validator pipeline (lint, typecheck, unit tests, docker build and smoke checks):

	make validate