# huisChecker

Dutch housing due-diligence application. Generates a structured report for a given address, drawing on publicly available data sources.

**Report-first:** huisChecker produces a per-address report, not a map or a valuation tool.

## Data sources (MVP)

| Source | What it provides |
|---|---|
| CBS | Postcode and regional statistics |
| BAG / PDOK | Address validation and building attributes |
| Leefbaarometer | Neighbourhood liveability scores |
| Politie | Crime and nuisance data per district |
| Klimaateffectatlas / Atlas Leefomgeving | Flood, heat, and drought risk layers |

## Stack

- **Backend:** FastAPI + Jinja2 templates
- **Frontend:** HTML + Tailwind CSS (CDN)
- **Environment:** Python 3.13, managed with `uv`
- **Tests:** pytest
- **Lint / format:** ruff

## Documentation layout

- `AGENTS.md`: shared root instruction file for coding agents
- `CLAUDE.md`: short Claude Code wrapper that imports `AGENTS.md`
- `docs-shared/`: project documentation tracked in git
- `docs-local/`: local-only notes and prompt chains (gitignored)

## Quick start

```bash
# Create or sync the environment
make sync

# Run the application (with hot-reload)
make dev

# Or run without hot-reload
make run
```

Open <http://127.0.0.1:8000> in your browser.

## Developer commands

| Command | Description |
|---|---|
| `make sync` | Create / sync the uv environment |
| `make run` | Run the app via `python -m huisChecker` |
| `make dev` | Run with uvicorn hot-reload |
| `make test` | Run pytest |
| `make lint` | Run ruff linter |
| `make format` | Run ruff formatter |
| `make check` | Lint + test together |

## Environment variables

Copy `.env.example` to `.env` and fill in any required values:

```bash
cp .env.example .env
```

## Directory structure

```
src/huisChecker/
├── app/            # FastAPI application, routes, templates, static files
├── contracts/      # Pydantic data contracts for external sources
├── etl/            # ETL pipeline per data source
├── layers/         # Map layer configuration and metadata
└── report/         # Report generation logic
tests/              # pytest test suite
docs-shared/        # Architecture, decisions, external references
docs-local/         # Private notes and prompt chains (gitignored)
```

## Notes

- No valuation, bidding, WOZ-led workflows, energy-label integration, or AI chat features.
- No opaque overall "huisChecker score" — each data source is presented separately.
