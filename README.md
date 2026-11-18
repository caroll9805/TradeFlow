# TradeFlow — Uzbekistan B2B Market Intelligence & Procurement Platform

TradeFlow helps businesses in Uzbekistan find manufacturers, wholesalers and distributors, compare their offers,
see the **cheapest** and the **best overall** procurement option, follow price history by region, and ask an AI
assistant market questions — with every number traceable to its source.

Built for hackathon challenge **№19 — Bozor-Analitika (B2B AI Platform)** as a production-oriented modular monolith.

| | |
|---|---|
| Frontend | React 18 + TypeScript + Vite, Tailwind CSS, shadcn-style UI primitives, React Router, TanStack Query, Recharts, React Hook Form + Zod, Leaflet/OpenStreetMap |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic |
| Data | PostgreSQL 16 + PostGIS (SQLite for tests) |
| Analytics / AI | pandas, NumPy, scikit-learn (robust z-score + IsolationForest, linear trend), pluggable LLM provider with deterministic fallback |
| Infra | Docker Compose, Nginx, background collection worker |

## Quick start on Windows 11

Start Docker Desktop, then double-click **`START_TRADEFLOW.cmd`** (builds the images, which installs all Python and
npm dependencies inside the containers, then runs migrations, seeds, starts everything and runs an end-to-end smoke
test). Then double-click **`RUN_TESTS.cmd`** for pytest, the TypeScript build and Vitest. All output goes to `logs\`.
Step-by-step PowerShell commands: `docs/WINDOWS_SETUP.md`. Problems: `docs/TROUBLESHOOTING.md`.

## Quick start (Docker, any OS)

```bash
cp .env.example .env          # then set POSTGRES_PASSWORD, JWT_SECRET (and optionally BOOTSTRAP_ADMIN_PASSWORD)
docker compose up --build
```

* App: <http://localhost:8080>  ·  API docs (OpenAPI): <http://localhost:8000/api/docs>
* On start the backend runs `alembic upgrade head`, seeds reference data (roles, 14 regions, units, 13 categories with
  attributes, data-source registry, business rules) and — when `SEED_DEMO=true` — a **clearly labelled SIMULATED demo dataset**.

Development with hot reload: `docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build`
(Vite on <http://localhost:5173>).

### Demo accounts (only created by the simulated demo seed)

| Role | Email | Password |
|---|---|---|
| Business buyer | `buyer@demo.example.com` | `Demo12345!` |
| Supplier (owns “[DEMO] Toshkent Qurilish Savdo”) | `supplier@demo.example.com` | `Demo12345!` |
| Market data administrator | `data@demo.example.com` | `Demo12345!` |
| Platform super administrator | `admin@demo.example.com` | `Demo12345!` |

> Never enable `SEED_DEMO` in a real deployment. Purge demo data any time: *Platform admin → Demo data*.

### Without Docker

```bash
# backend
cd backend && python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
export DATABASE_URL=postgresql+psycopg://tradeflow:pass@localhost:5432/tradeflow JWT_SECRET=dev-secret
alembic upgrade head && python -m app.seed --demo && uvicorn app.main:app --reload
python -m app.worker            # optional: scheduled connectors
# frontend
cd frontend && npm install && npm run dev
```

## What is implemented

* **Auth & RBAC** — register (buyer / supplier / manufacturer), login, access + refresh JWT with revocation,
  bcrypt hashing, rate-limited auth endpoints, 6 roles with DB-stored permissions, organization isolation and
  object-level checks on every write (suppliers can only touch their own organization's profiles/offers; quote
  requests are visible only to the buyer org and the supplier org).
* **Universal catalog** — 13 categories from day one (food, electronics, textiles, cosmetics, construction, industrial,
  furniture, auto parts, office, agriculture, medical (with compliance notice), packaging, other). Category attributes
  (text/number/boolean/date/select/multiselect, required, filterable, matching key) are **created in the admin UI**
  and drive product forms, validation and catalog filters.
* **Units** — dimension-based conversion (kg↔t↔g, l↔ml↔m³…) plus product-specific conversions (bag = 50 kg, box = 24 pcs).
  Incompatible units are rejected; prices are compared only per normalised base unit.
* **Suppliers** — directory, profiles, locations (exact coordinates only if supplied), categories, ratings,
  verification request → admin review; *registered ≠ verified*.
* **Offers & comparison** — original price/currency kept, conversion to UZS with a **recorded** exchange rate,
  MOQ, stock, delivery (declared cost only — unknown costs are flagged, never invented), validity, price type,
  provenance. Deterministic **total procurement cost** and a transparent **best overall** score
  (price, reliability, freshness, stock, distance) with admin-editable weights and a per-offer breakdown.
* **Price history** — every offer creation/price change and every import row creates an immutable
  `price_observations` record; day/week/month aggregation, regional comparison, movers, anomaly detection,
  guarded forecast (shown only with ≥8 weekly points and always labelled *estimate*).
* **Supply & activity indicators** — observed supply, declared stock, search interest, quote requests and verified
  transactions are kept separate; missing figures show **Insufficient data**.
* **AI market assistant** — uz/ru/en; resolves product, region, quantity and intent, runs backend queries and
  answers only from results, with sources and disclaimers. Works without any API key (deterministic engine); set
  `LLM_PROVIDER` (`openai_compatible` or `anthropic`) to let an LLM parse questions and phrase answers from the
  same tool output.
* **Market Data Engine** — source registry with legal/technical review fields, connector registry
  (`file_import`, `http_json`, `supplier_submission`, `manual_entry`), per-connector health metrics, scheduled worker,
  CSV/XLSX import (uz/ru/en headers), validation, product matching (barcode → SKU → normalised name → fuzzy) with a
  **human review queue**, duplicate detection, data-quality scoring, full provenance, job logs.
* **Dashboards & UI** — landing, auth, market dashboard, catalog, product detail/comparison, supplier directory and
  profile, price analytics, regional analytics with Leaflet map, AI assistant, saved items, procurement workspace,
  supplier dashboard, market-data admin, platform admin, settings. Uzbek / Russian / English UI from one translation
  table; Asia/Tashkent time, UZS formatting.
* **Admin** — users, roles/permissions matrix, categories & attributes, units, regions, business rules
  (ranking weights, thresholds), exchange rates, audit log, subscription plans (billing not implemented), demo purge.

## Tests

```bash
docker compose run --rm backend pytest            # backend (uses in-memory SQLite)
cd frontend && npm install && npm test             # frontend (Vitest + Testing Library)
cd frontend && npm run build                       # type-check + production build
```

**Test execution status (run on Windows 11 + Docker Desktop, 18 Nov 2026, via `RUN_TESTS.cmd`).** The Docker builds
install all dependencies, using pip and npm inside the images. Every step passed (`logs\test-summary.txt`):

| Step | Result |
|---|---|
| Image rebuild (backend + frontend) | OK |
| `docker compose up --wait` | db, backend, worker and frontend all healthy |
| backend `pytest` | **59 passed** |
| `alembic current` | `0001_baseline (head)` |
| frontend `npm ci`, `tsc --noEmit`, `vite build` | OK (chunk-size warning only) |
| frontend Vitest | **13 passed** (2 files) |
| `python -m app.smoke` via the Nginx proxy | **21/21 passed** |

See `docs/TESTING.md` for details.

## Documentation

* `docs/ARCHITECTURE.md` — modules, request flow, AI and data-engine design, security
* `docs/DATABASE.md` — schema
* `docs/API.md` — endpoint reference (live OpenAPI at `/api/docs`)
* `docs/DATA_SOURCES.md` — connector guide and candidate-source review status
* `docs/TESTING.md`, `docs/DEMO.md` (hackathon script), `docs/ROADMAP.md` (known limitations & next steps)

## Data honesty rules (enforced in code)

1. No fabricated suppliers, prices or statistics outside the **SIMULATED** demo dataset, which is flagged
   `is_simulated`, uses provenance `simulated`, prefixes supplier names with `[DEMO]`, is bannered in the UI, can be
   hidden with one switch and purged with one action.
2. Asking prices are never presented as transactions; provenance kinds are always shown.
3. No candidate source is integrated: automated collection is blocked until an admin records that the source's terms
   permit it; connectors never bypass logins, CAPTCHAs or anti-bot measures.
4. Calculations (costs, averages, changes, scores) are deterministic backend code; the LLM never computes them.
