.PHONY: format test batch batch-dry-run docker-debug-shell

COMPOSE_FILE ?= docker-compose.yml
AUTOFIX_RUN_TIMEOUT_SECONDS ?= 300s

format:
	uv run ruff format .

test:
	uv run python -m unittest discover -s tests -p "test_*.py"

batch:
	uv run autofix batch $(BATCH_CONFIG)

batch-dry-run:
	uv run autofix batch $(BATCH_CONFIG) --dry-run

docker-debug-shell:
	docker compose -f $(COMPOSE_FILE) run --rm --build --entrypoint /bin/sh runner