.PHONY: check fix format lint typecheck test validate run docker-build docker-smoke contracts-smoke agent-smoke compose-up compose-down compose-ps compose-smoke

RUNNER_IMAGE ?= llm-autofix-runner:py313
RUNNER_DOCKERFILE ?= docker/runtime.Dockerfile
COMPOSE_FILE ?= docker-compose.yml

check: lint typecheck

lint:
	uv run ruff check .
	uv run ruff format --check .

fix:
	uv run ruff check . --fix
	uv run ruff format .

format:
	uv run ruff format .

typecheck:
	uv run mypy src

test:
	uv run python -m unittest discover -s tests -p "test_*.py"

validate: check test docker-build docker-smoke contracts-smoke

run:
	uv run autofix

docker-build:
	docker build -f $(RUNNER_DOCKERFILE) -t $(RUNNER_IMAGE) .

docker-smoke:
	uv run autofix docker-smoke --repo . --image $(RUNNER_IMAGE) --command "python --version"

contracts-smoke:
	uv run autofix contracts-smoke

agent-smoke:
	uv run autofix agent-smoke

compose-up:
	docker compose -f $(COMPOSE_FILE) up -d --build runner

compose-down:
	docker compose -f $(COMPOSE_FILE) down

compose-ps:
	docker compose -f $(COMPOSE_FILE) ps

compose-smoke:
	docker compose -f $(COMPOSE_FILE) run --rm runner uv run autofix agent-smoke