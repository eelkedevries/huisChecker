# huisChecker

Dutch housing due-diligence application. Generates a structured report for a given address, drawing on publicly available data sources.

**Report-first:** huisChecker produces a per-address report, not a map or a valuation tool.

## Data sources (MVP)

| Source | Access mode | What it provides |
|---|---|---|
| PDOK Locatieserver | Remote (live, nationwide) | Address search and resolution |
| BAG / PDOK | Remote (live, per address) + minimal local subset fallback | Building attributes |
| CBS kerncijfers per PC4 | Remote (OData StatLine) + minimal local subset fallback | Postcode / regional statistics |
| Leefbaarometer | Minimal local subset (scope-limited) | Neighbourhood liveability bands |
| Politie open data | Remote (when configured) + minimal local subset fallback | Crime and nuisance rates |
| Klimaateffectatlas / Atlas Leefomgeving | Remote WMS overlay + minimal local subset fallback | Flood / heat / noise classes |

Address search hits PDOK Locatieserver live, so any Dutch address resolves.
Enrichment modules run through per-source remote adapters that are
**scope-gated** — only the currently configured pc4 / municipality /
province keys ever trigger a remote call or are kept in the local cache.

## Current geographic scope

The current test scope is narrow and deliberate:

| Key | Default value |
|---|---|
| `HC_SCOPE_PC4` | `2316` |
| `HC_SCOPE_MUNICIPALITIES` | `GM0546` (Leiden) |
| `HC_SCOPE_PROVINCES` | `PV28` (Zuid-Holland) |

The scope is a whitelist: adapters short-circuit for any pc4 outside it.
Expanding coverage is a configuration change — set the env vars to
comma-separated lists — not a code change.

## Stack

- **Backend:** FastAPI + Jinja2 templates
- **Frontend:** HTML + Tailwind CSS (CDN) + Leaflet (WMS for remote layers)
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
make sync
make dev            # hot-reload
# or:
make run
```

Open <http://127.0.0.1:8000>.

## Developer commands

| Command | Description |
|---|---|
| `make sync` | Create / sync the uv environment |
| `make run` | Run the app via `python -m huisChecker` |
| `make dev` | Run with uvicorn hot-reload |
| `make test` | Run pytest |
| `make lint` / `format` / `check` | Ruff linter / formatter / lint + tests |
| `make etl-smoke` | Fixture-mode ETL smoke run |
| `make scope-refresh` | Refresh cache + subset for the current scope |
| `make scope-validate` | Verify every scope pc4 has data via adapters |
| `make scope-smoke` | Refresh + validate, CI-friendly |

## Environment variables

Copy `.env.example` to `.env` and fill in any required values. The file
documents the PDOK, CBS, BAG, politie and KEA endpoints; the scope
whitelist; and the free-report testing mode.

### Free-report testing mode

Local development defaults to free full reports so the preview → report
flow can be exercised without Mollie. Requires `REPORT_FREE_ACCESS=1`
**and** `APP_ENV=development`. Production never serves free reports.
An amber "Ontwikkelmodus" banner shows on the preview + report pages
when the mode is active.

## Remote-first architecture

- `src/huisChecker/address/` — PDOK live search/resolution (nationwide).
- `src/huisChecker/remote/` — scope-gated source adapters. Each adapter
  has a `fetch_pc4(pc4)` (or `fetch_object(bag_object_id)`) that
  tries cache → live → minimal local subset fallback. Cache files live
  under `data/cache/<adapter>/<key>.json`.
- `src/huisChecker/scope.py` — single source of truth for the current
  pc4 / municipality / province whitelist.
- `src/huisChecker/layers/` — overlay registry; remote-only layers use
  `RemoteTileConfig` (WMS) and are rendered directly by the map partial.
- `data/curated/` — minimal local subset. Only in-scope rows are needed
  to run the app; the ETL smoke path still generates the demo rows for
  unit tests.
- `src/huisChecker/etl/fixtures/pc4_boundaries.geojson` —
  authoritative irregular PC4 polygons (simplified from PDOK / CBS)
  bundled with the repo; layer-producing ETL jobs join their values
  against this file instead of the earlier bbox stub.

## Leefbaarometer overlay

- **Authoritative geometry.** PC4 polygons come from
  `pc4_boundaries.geojson`; no more axis-aligned rectangles.
- **Area comparison.** The overlay paints every PC4 in the current map
  extent with its source-native Leefbaarometer band, so neighbouring
  areas are visible alongside the selected one.
- **Selection highlight.** The PC4 that matches
  `data-focus-postcode4` is drawn with a stronger stroke; its
  neighbours keep a lighter, dashed outline.
- **Overall score is primary.** The report + preview cards lead with
  the overall Leefbaarometer score/class and peiljaar. The five
  official dimensions (Woningvoorraad, Fysieke omgeving,
  Voorzieningen, Sociale samenhang, Overlast en onveiligheid) are
  shown as a compact block when the source publishes them for the
  selected PC4.
- **No composite.** huisChecker does not synthesise the dimensions
  into a custom score. Dimension overlays are intentionally *not*
  registered: the MVP data path only carries dimension scores for one
  PC4, so a dimension overlay would offer no comparison — expose it
  only once Leefbaarometer publishes the dimensions per PC4 across the
  active scope.

## Expanding scope later

1. Add the new pc4 / municipality / province codes to
   `HC_SCOPE_PC4` / `HC_SCOPE_MUNICIPALITIES` / `HC_SCOPE_PROVINCES`.
2. Run `make scope-refresh` to prime the cache for the new scope.
3. Run `make scope-validate` to confirm coverage.
4. If a source has no remote, add the additional rows to the fixtures
   under `src/huisChecker/etl/fixtures/` and rerun `make etl-smoke`.

## Directory structure

```
src/huisChecker/
├── address/         # PDOK search/resolution + preview assembly
├── app/             # FastAPI app, routes, templates, static
├── contracts/       # Pydantic data contracts
├── etl/             # ETL pipeline + scope_cli
├── layers/          # Layer registry (local geojson + remote WMS)
├── remote/          # Remote-first source adapters
├── report/          # Full report assembly
└── scope.py         # Geographic scope whitelist
data/
├── curated/         # Minimal local subset (CSV + GeoJSON)
├── cache/           # Remote-adapter payload cache
└── manifests/       # ETL manifests (periods, licences, caveats)
```

## Notes

- No valuation, bidding, WOZ-led workflows, energy-label integration, or AI chat features.
- No opaque overall "huisChecker score" — each data source is presented separately.
- Test scope is currently narrow (2316 / Leiden / Zuid-Holland). Widening
  scope is a config change, not a rewrite.
