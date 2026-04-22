# huisChecker

Dutch housing due-diligence application. Generates a structured report for a given address, drawing on publicly available data sources.

**Report-first:** huisChecker produces a per-address report, not a map or a valuation tool.

## Data sources (MVP)

| Source | What it provides |
|---|---|
| PDOK Locatieserver | Live nationwide address search and resolution (primary lookup) |
| BAG / Kadaster | Local building attributes (construction year, surface, use) — enrichment only |
| CBS | Postcode and regional statistics — enrichment only |
| Leefbaarometer | Neighbourhood liveability scores — enrichment only |
| Politie | Crime and nuisance data per district — enrichment only |
| Klimaateffectatlas / Atlas Leefomgeving | Flood, heat, and noise risk layers — enrichment only |

Address search hits PDOK Locatieserver live, so any Dutch address resolves.
Enrichment layers (BAG, CBS, Leefbaarometer, police, climate) come from curated
local datasets; addresses outside the curated footprint still render as a
partial preview with a clear notice about the missing layers.

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

### Free-report testing mode

Local development defaults to free full reports so the preview → report flow
can be exercised without going through Mollie checkout. The flag is guarded
by two env vars and only flips to free when **both** conditions hold:

| Variable | Dev default | Behaviour |
|---|---|---|
| `APP_ENV` | `development` | Production never serves free reports via env flag |
| `REPORT_FREE_ACCESS` | `1` | Set to `0` to exercise the paid checkout locally |

When free mode is active:

- the preview CTA links straight to `/report?id=…` (bypasses `/checkout`)
- the preview and report pages show an amber "Ontwikkelmodus" banner
- the existing Mollie/Tokenised flow is kept intact and re-enables as soon
  as either env var is flipped.

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
