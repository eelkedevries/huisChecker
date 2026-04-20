# Decisions

## 2026-04-20 — FastAPI + Jinja2 as web stack

**Decision:** Use FastAPI with Jinja2 server-side templates and Tailwind CSS via CDN.

**Rationale:** The project is Python-native (uv, pytest, ruff). FastAPI is modern, well-typed, and easy to extend. Jinja2 keeps the report rendering server-side, which suits a report-first product. Tailwind CDN avoids a Node.js build step in the initial scaffold.

**Implications:** Frontend interactivity (e.g., address autocomplete, map layers) will be added incrementally via htmx or a lightweight JS approach in later prompts.

---

## 2026-04-20 — No composite score

**Decision:** Present each data source as a separate report section. Do not aggregate into a single "huisChecker score".

**Rationale:** An opaque composite score obscures the underlying data and misleads buyers about weightings. Users should apply their own judgement.

**Implications:** Report UI must make per-section findings easy to read without implying relative importance.

---

## 2026-04-20 — Five MVP data source groups

**Decision:** Limit the MVP to CBS, BAG/PDOK, Leefbaarometer, Politie, and Klimaateffectatlas / Atlas Leefomgeving.

**Rationale:** These cover the core due-diligence dimensions (area statistics, building facts, liveability, safety, climate risk) and are all Dutch public open data.

**Implications:** Other sources (e.g., school proximity, noise maps) are out of scope for the MVP but can be added as new ETL modules later.
