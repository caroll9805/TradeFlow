# Architecture

TradeFlow is a **modular monolith**: one FastAPI application with clear internal modules, one PostgreSQL database,
one background worker process and a static SPA served by Nginx. Microservices were deliberately not introduced —
the modules have clean seams (services layer, connector registry, provider abstraction) so they can be split later.

```
browser ── Nginx (SPA + /api proxy) ── FastAPI (app.main)
                                          ├─ api/routes/*        HTTP layer, validation (Pydantic), authZ deps
                                          ├─ services/*          business logic (no HTTP)
                                          │   ├─ comparison      deterministic total cost + scoring
                                          │   ├─ analytics       history, movers, regional, supply/demand, anomalies, forecast
                                          │   ├─ pricing/units/currency/matching/text
                                          │   ├─ market_data/    connector interface + registry + shared pipeline
                                          │   └─ assistant/      intent parsing, tools, LLM provider abstraction
                                          ├─ models/*            SQLAlchemy 2 ORM
                                          └─ seed/               reference seed + SIMULATED demo seed
worker (app.worker) ── runs due connectors ── same services + DB
PostgreSQL 16 + PostGIS
```

## Folder structure

```
TradeFlow/
├─ backend/
│  ├─ app/{core,models,schemas,api/routes,services,seed}/  main.py  worker.py
│  ├─ alembic/ (env.py, versions/0001_baseline.py)
│  ├─ tests/   Dockerfile  entrypoint.sh  requirements*.txt
├─ frontend/
│  ├─ src/{lib,components,components/ui,pages,pages/admin,locales,test}/
│  ├─ scripts/ (i18n source table + generator)  Dockerfile  nginx.conf
├─ docs/  sample_data/  docker-compose.yml  docker-compose.dev.yml  .env.example
```

## Key design decisions

**No hardcoded business data.** Categories, attributes, options, units, regions, data sources, ranking weights,
freshness thresholds, matching thresholds, analytics parameters, roles/permissions and subscription plans are rows in
the database, seeded once and editable in the admin panel. Code only contains technical fallbacks
(`services/settings_service.py`) used if a setting row is missing.

**Prices.** `offers` holds the *current* offer; `price_observations` is the append-only history. Every offer create or
price change calls `pricing.apply_offer_price`, which converts currency with a recorded `exchange_rates` row (stored
on the offer/observation with its date), normalises to the product base unit, and appends an observation. Observation
price fields are never updated; only review metadata (verification, outlier flag) can change.

**Comparison (services/comparison.py).** For each active offer: unit-normalised price, order quantity (MOQ, whole
packages), goods cost, declared delivery cost (unknown cost ⇒ flagged and not eligible for "best"), fees, effective
price per base unit, stock coverage, freshness (age vs category/source threshold), reliability (verification,
source reliability, rating), proximity (distance between region centres). Score = Σ weight × criterion; weights come
from `platform_settings.ranking.weights`. The response includes the breakdown and a plain-language explanation.

**Market Data Engine.** `SourceConnector` subclasses only *collect raw records*. `pipeline.ingest_record` does
validation → product matching (barcode/SKU/normalised/fuzzy, thresholds from settings; uncertain → `product_matches`
review queue, never auto-merged) → supplier resolution → duplicate detection → currency/unit normalisation → quality
scoring → storage with provenance. `run_collection` wraps each row in a savepoint so one bad row never aborts a job,
and records job counters and row-level logs. Connectors that require it refuse to run unless the data source's
`terms_status` is `permitted`.

**AI assistant.** `assistant/engine.py`: language detection (uz/ru/en), entity resolution against DB names, synonyms
and aliases (region aliases and product `search_terms` are data), intent detection, tool execution
(`compare_offers`, `regional_prices`, `price_movers`, `regional_overview`), answer composition from tool output only.
With `LLM_PROVIDER` configured, the LLM produces the structured tool call and phrases the final answer from the JSON
result (temperature 0, instructed not to invent). Any LLM failure falls back to the deterministic answer and says so.

**Analytics.** pandas aggregation for history and movers; robust z-score (median/MAD) for anomalies with an
IsolationForest cross-check once a product has enough observations; scikit-learn linear trend for forecasts only when
the configured minimum of weekly points exists, labelled *estimate*.

## Security

* bcrypt password hashing; JWT access (30 min) + refresh (14 days) tokens; refresh tokens revoked by a per-user
  `token_version` (logout, password change, role change, deactivation).
* Authorization on the server: permission dependencies (`require(...)`), organization membership checks and
  object-level checks (`ensure_can_manage_supplier`). Cross-org reads return 404 to avoid leaking existence.
* Pydantic validation on all input; SQLAlchemy parameter binding (no string SQL); uploads limited by size and
  extension with XLSX magic-byte check; JSON-only API; React escapes output; CSP and security headers from Nginx/API.
* Sliding-window rate limits on auth and assistant endpoints (in-process; swap the store for Redis when scaling out).
* Secrets only via environment; production start refuses the default JWT secret; generic 500 responses.
* Audit log for logins, registrations, verification, catalog/config changes, imports, purges.
* Not claimed: compliance with Uzbekistan's personal-data law (ZRU-547) or medical-goods regulation — these need legal review.

## Scaling path

Read replicas / materialised views for analytics, Redis for rate limits and caching, Celery/RQ for collection jobs,
PostGIS geometry columns for warehouses and service areas, object storage for images, then extraction of the market
data engine as a separate service if ingestion volume requires it.
