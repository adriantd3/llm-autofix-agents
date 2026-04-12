.PHONY: check fix format lint typecheck test validate run docker-build docker-smoke contracts-smoke agent-smoke

RUNNER_IMAGE ?= llm-autofix-runner:py313
RUNNER_DOCKERFILE ?= docker/runner.Dockerfile

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