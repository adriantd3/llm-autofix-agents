.PHONY: format test run compose-up compose-down compose-smoke quixbugs-gcd-run

COMPOSE_FILE ?= docker-compose.yml

format:
	uv run ruff format .

test:
	uv run python -m unittest discover -s tests -p "test_*.py"

run:
	uv run autofix run

compose-up:
	docker compose -f $(COMPOSE_FILE) up -d --build runner

compose-down:
	docker compose -f $(COMPOSE_FILE) down

compose-smoke:
	timeout $${AUTOFIX_RUN_TIMEOUT_SECONDS:-180s} docker compose -f $(COMPOSE_FILE) exec -T runner sh -lc 'echo "[runner] entered container"; exec uv run autofix run'

quixbugs-gcd-run:
	timeout $${AUTOFIX_RUN_TIMEOUT_SECONDS:-180s} docker compose -f $(COMPOSE_FILE) exec -T runner sh -lc 'echo "[runner] entered container"; exec uv run autofix run'