# Testing

## Backend (pytest)
```bash
docker compose run --rm backend pytest            # or: cd backend && pip install -r requirements-dev.txt && pytest
```
Tests use an in-memory SQLite database created from the models and the reference seed (`tests/conftest.py`).

| File | Covers |
|---|---|
| `test_auth.py` | registration (buyer/supplier), password policy, duplicate email, login, refresh rotation, logout revocation, token-type confusion, disabled users |
| `test_authorization.py` | permission checks, anonymous access, cross-supplier offer/profile edits (403), self-verification blocked, admin verification + audit log, quote isolation between organizations, role changes, ratings |
| `test_catalog.py` | 13 seeded categories, 14 regions, admin-created category with dynamic attributes, attribute validation (required / select / number / foreign attribute), attribute filters, multilingual search, supplier vs admin product rights, archiving |
| `test_units_matching.py` | unit conversions, incompatible units, product-specific and chained conversions, unit aliases, text normalisation, barcode/fuzzy matching |
| `test_offers_comparison.py` | normalisation, history preserved on price changes, incompatible units, currency conversion requiring a recorded rate, cheapest vs best overall with MOQ/stock/delivery, unknown delivery cost, regional filter & regional prices, expired offers, input validation |
| `test_market_data.py` | CSV import end-to-end (stored / duplicate / review / rejected rows, provenance, logs, match accept/reject), XLSX offer import with uz headers, bad files, `http_json` blocked until terms permitted, mocked API collection, 403 handling, manual observation + verification |
| `test_assistant_analytics.py` | assistant in en/ru/uz (cheapest, region comparison, suppliers in region, minimum quantity, no invented answers), price history & movers, guarded forecast, supply/demand separation, overview & regions, demo seed labelling and purge safety, anomaly detection |

## Frontend (Vitest + Testing Library)
```bash
cd frontend && npm install && npm test && npm run build
```
`src/test/lib.test.ts` (formatting, query strings, API error mapping, locale key parity uz/ru/en) and
`src/test/pages.test.tsx` (login validation/success/failure, catalog search & category filtering & error state,
offer comparison highlights and quantity request, dashboard KPIs, admin purge requiring confirmation, empty/error states).
API calls are mocked at `fetch`.

## Integration checks
* `docker compose up --build` → backend health check (`/api/health`) gates the worker; migrations and seed run on start.
* CSV import: upload `sample_data/sample_price_list.csv` in *Market data → Import*.
* Connector error handling: create an `http_json` connector for a source whose terms are not `permitted` and press
  *Run now* — the job fails with an explanatory error and the connector shows the error status.

## Execution status
All suites run inside Docker on the target machine (Windows 11, Docker Desktop). The authoring sandbox has no PyPI/npm
access. These are the results of the latest `RUN_TESTS.cmd` run (18 Nov 2026), all exit code 0:

| Check | Result |
|---|---|
| Rebuild images (pip install + import check; npm ci) | OK |
| `docker compose up -d --wait` | db, backend, worker, frontend healthy |
| `pytest` | **59 passed** |
| `alembic current` | `0001_baseline (head)` |
| Frontend `tsc --noEmit` + `vite build` | OK (bundle-size warning only) |
| Vitest | **13 passed** (`lib.test.ts` 5, `pages.test.tsx` 8) |
| `python -m app.smoke` via Nginx proxy | **21/21 passed**: health, SPA + deep link, 14 regions, 13 categories, register, /auth/me, RBAC 403/401, overview, search, compare, history, demo admin/buyer/supplier/data logins, admin sources/audit/simulated flag, assistant |

Bugs found and fixed through these runs:
* Demo and bootstrap accounts used the reserved `.local` domain, which `EmailStr` rejects, so demo logins failed.
  Accounts are now `@demo.example.com`, and existing databases and `.env` files are migrated on start. Covered by
  `test_demo_accounts_can_log_in` and `test_bootstrap_admin_default_email_is_valid`.
* The smoke test skipped admin checks silently. It now fails loudly.
* The worker inherited the backend's HTTP health check. That check is now disabled for the worker.
* `# syntax=docker/dockerfile:1.7` made every build depend on Docker Hub. It was removed, because cache mounts work without it.

Run everything with `RUN_TESTS.cmd` (or `scripts\test.ps1`). It writes one log per step to `logs\` and the
summary to `logs\test-summary.txt`.
