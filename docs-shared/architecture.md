# Architecture

## Purpose

huisChecker is a report-first Dutch housing due-diligence application. Given a Dutch address, it fetches data from five public data source groups and produces a structured, per-section report. It does not provide a single composite score.

## Major components

```
Browser
  └── FastAPI app (src/huisChecker/app/)
        ├── Routes: /, /explore, /address, /report, /methodology
        ├── Templates: Jinja2 (base.html + per-page)
        └── Static: CSS

FastAPI app
  └── report/ (report assembly per address)
        └── etl/ (one module per data source)
              ├── CBS (postcode & regional statistics)
              ├── BAG / PDOK (address & building)
              ├── Leefbaarometer (liveability)
              ├── Politie (crime & nuisance)
              └── Klimaateffectatlas / Atlas Leefomgeving (climate risk)

contracts/  — Pydantic models, one per source
layers/     — Map layer configuration and metadata
```

## Data flow

1. User submits an address on the homepage.
2. `/address` validates the address against BAG/PDOK.
3. `/report` triggers ETL for each source, assembles a report object, and renders it via Jinja2.
4. Each report section maps to one data source; sections are independent.

## Assumptions and constraints

- Report-first, not map-first.
- No valuation, bidding, WOZ-led, energy-label, or AI-chat features.
- No opaque overall score.
- All data sources are Dutch public open data (no paid APIs in the MVP).
- Python 3.13, uv, FastAPI, Jinja2, Tailwind CDN.
