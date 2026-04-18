.PHONY: format test run compose-up compose-down compose-smoke

COMPOSE_FILE ?= docker-compose.yml

format:
	uv run ruff format .

test:
	uv run python -m unittest discover -s tests -p "test_*.py"

run:
	uv run autofix

compose-up:
	docker compose -f $(COMPOSE_FILE) up -d --build runner

compose-down:
	docker compose -f $(COMPOSE_FILE) down

compose-smoke:
	docker compose -f $(COMPOSE_FILE) run --rm runner uv run autofix agent-smoke