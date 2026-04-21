.PHONY: sync run dev test lint format check etl-import etl-refresh etl-validate etl-smoke

sync:
	uv sync

run:
	uv run python -m huisChecker

dev:
	uv run uvicorn huisChecker.app.main:app --reload --host 127.0.0.1 --port 8000

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

check:
	uv run ruff check .
	uv run pytest

etl-import:
	uv run python -m huisChecker.etl.cli import

etl-refresh:
	uv run python -m huisChecker.etl.cli refresh

etl-validate:
	uv run python -m huisChecker.etl.cli validate

etl-smoke:
	uv run python -m huisChecker.etl.cli smoke
