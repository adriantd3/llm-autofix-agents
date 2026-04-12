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

5. Run baseline agent smoke (uses `LLM_PROVIDER` and provider keys from environment):

	make agent-smoke

6. Run full validator pipeline (lint, typecheck, unit tests, docker build and smoke checks):

	make validate