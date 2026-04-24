.PHONY: sync run dev test lint format check etl-import etl-refresh etl-validate etl-smoke scope-refresh scope-validate scope-smoke

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

# --- scope-limited remote + local subset refresh -----------------------------
# These targets operate on the scope defined by HC_SCOPE_* env vars (default:
# postcode4 2316, Leiden GM0546, Zuid-Holland PV28). They refresh the small
# cache under data/cache and the curated subset so the app can run offline
# for the current test footprint.
scope-refresh:
	uv run python -m huisChecker.etl.cli refresh
	uv run python -m huisChecker.etl.scope_cli refresh

scope-validate:
	uv run python -m huisChecker.etl.cli validate
	uv run python -m huisChecker.etl.scope_cli validate

scope-smoke:
	uv run python -m huisChecker.etl.cli smoke
	uv run python -m huisChecker.etl.scope_cli smoke
