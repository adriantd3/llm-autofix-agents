.PHONY: check fix format lint typecheck

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

run:
	uv run autofix