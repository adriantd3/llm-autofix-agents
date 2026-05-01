.PHONY: format test run docker-run docker-debug-shell quixbugs-gcd-run quixbugs-gcd-mono quixbugs-gcd-handoff

COMPOSE_FILE ?= docker-compose.yml
AUTOFIX_RUN_TIMEOUT_SECONDS ?= 300s

RUN_REPOSITORY ?=
RUN_BRANCH ?=
RUN_ARCHITECTURE ?=
RUN_AGENT_MODELS ?=
RUN_BOOTSTRAP_PROMPT ?=
RUN_TEST_COMMAND ?=

LLM_PROVIDER ?=
LLM_MODEL ?=
OLLAMA_BASE_URL ?=
OLLAMA_API_KEY ?=
OPENAI_API_KEY ?=
OPENAI_BASE_URL ?=
GEMINI_API_KEY ?=
GEMINI_BASE_URL ?=

AUTOFIX_LOG_LEVEL ?=
AUTOFIX_RESULTS_DIR ?=
AUTOFIX_OBSERVABILITY_DB ?=
AUTOFIX_INTERACTIVE ?=

format:
	uv run ruff format .

test:
	uv run python -m unittest discover -s tests -p "test_*.py"

run:
	uv run autofix run

docker-run:
	HOST_UID=$$(id -u) HOST_GID=$$(id -g) \
	RUN_REPOSITORY="$(RUN_REPOSITORY)" RUN_BRANCH="$(RUN_BRANCH)" RUN_ARCHITECTURE="$(RUN_ARCHITECTURE)" RUN_AGENT_MODELS='$(RUN_AGENT_MODELS)' RUN_BOOTSTRAP_PROMPT="$(RUN_BOOTSTRAP_PROMPT)" RUN_TEST_COMMAND="$(RUN_TEST_COMMAND)" LLM_PROVIDER="$(LLM_PROVIDER)" LLM_MODEL="$(LLM_MODEL)" OLLAMA_BASE_URL="$(OLLAMA_BASE_URL)" OLLAMA_API_KEY="$(OLLAMA_API_KEY)" OPENAI_API_KEY="$(OPENAI_API_KEY)" OPENAI_BASE_URL="$(OPENAI_BASE_URL)" GEMINI_API_KEY="$(GEMINI_API_KEY)" GEMINI_BASE_URL="$(GEMINI_BASE_URL)" AUTOFIX_LOG_LEVEL="$(AUTOFIX_LOG_LEVEL)" AUTOFIX_RESULTS_DIR="$(AUTOFIX_RESULTS_DIR)" AUTOFIX_OBSERVABILITY_DB="$(AUTOFIX_OBSERVABILITY_DB)" AUTOFIX_INTERACTIVE="$(AUTOFIX_INTERACTIVE)" \
	timeout --foreground $${AUTOFIX_RUN_TIMEOUT_SECONDS:-$(AUTOFIX_RUN_TIMEOUT_SECONDS)} docker compose -f $(COMPOSE_FILE) run --rm -T --build runner

docker-debug-shell:
	docker compose -f $(COMPOSE_FILE) run --rm --build --entrypoint /bin/sh runner

quixbugs-gcd-run:
	$(MAKE) docker-run RUN_REPOSITORY="https://github.com/jkoppel/QuixBugs.git" RUN_BRANCH="master" RUN_TEST_COMMAND="uv run --with pytest pytest python_testcases/test_gcd.py"

quixbugs-gcd-mono:
	$(MAKE) quixbugs-gcd-run RUN_ARCHITECTURE="mono_agent"

quixbugs-gcd-handoff:
	$(MAKE) quixbugs-gcd-run RUN_ARCHITECTURE="multi_agent_handoff"