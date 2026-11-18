# API reference

Base path `/api`. JSON in/out. Auth: `Authorization: Bearer <access_token>`. Interactive OpenAPI docs: `/api/docs`.
Lists are paginated: `?page=1&page_size=20` → `{items, total, page, page_size}`. Errors: `{"detail": ...}`
(422 validation errors list the field path).

## Auth
| Method | Path | Notes |
|---|---|---|
| POST | `/auth/register` | buyer / supplier / manufacturer; creates organization (+ unverified supplier profile) |
| POST | `/auth/login` | → `{access_token, refresh_token}` (rate limited) |
| POST | `/auth/refresh` | rotates tokens; rejects revoked refresh tokens |
| POST | `/auth/logout` | revokes refresh tokens |
| GET/PATCH | `/auth/me` | profile |
| POST | `/auth/me/password` | change password (revokes sessions) |

## Reference (public)
`GET /regions`, `/regions/{id}/districts`, `/units`, `/unit-conversions?product_id=`, `/categories?with_attributes=&include_inactive=`,
`/categories/{id}` (with attributes and options), `/exchange-rates`, `/connector-types`.

## Products
| Method | Path | Notes |
|---|---|---|
| GET | `/products` | `q, category_id, brand, region_id, manufacturer_id, origin_type, price_type, price_min, price_max, has_offers, include_simulated, attrs` (JSON `{attribute_id: value}`), `sort` (name, price_asc, price_desc, offers, updated); items include `offer_stats` |
| GET | `/products/brands` | distinct brands |
| GET | `/products/{id}` | detail |
| POST | `/products` | `products.create`; attributes validated against the category definition |
| PUT/DELETE | `/products/{id}` | `catalog.manage` (DELETE archives) |
| GET | `/products/{id}/compare` | `quantity` (base units), `region_id`, `buyer_region_id`, `price_type`, `verified_only`, `include_simulated` → cheapest, best, weights, explanation, per-offer cost & score breakdown & provenance |
| GET | `/products/{id}/regional` | min/avg/max per region |
| GET | `/products/{id}/history` | `granularity` day/week/month, `days`, `region_id`, `price_type` |
| GET | `/products/{id}/forecast` | estimate or `insufficient_data` |
| GET | `/products/{id}/supply-demand` | separated indicators |
| GET | `/products/{id}/observations` | provenance records |
| GET/POST | `/manufacturers` | list / create |

## Suppliers
`GET /suppliers` (filters: q, region_id, category_id, supplier_type, verified_only, product_id, sort),
`GET /suppliers/mine`, `GET /suppliers/{id}` (with offers), `POST /suppliers`, `PUT /suppliers/{id}` (owner org or admin),
`POST /suppliers/{id}/verification-request?evidence=`, `POST /suppliers/{id}/verification` (`suppliers.verify`),
`POST /suppliers/{id}/ratings` (`quotes.request`).

## Offers
`GET /offers` (filters), `GET /offers/mine`, `POST /offers` (owner org), `PATCH /offers/{id}` (price change ⇒ new
observation), `DELETE /offers/{id}` (deactivate), `POST /offers/{id}/verification?status=` (`market_data.manage`).

## Analytics
`GET /analytics/overview`, `/analytics/movers`, `/analytics/regions`, `/analytics/freshness`, `/analytics/recent-offers`,
`/analytics/anomalies` (`market_data.manage`). All accept `include_simulated`.

## AI assistant
`GET /assistant/status`, `POST /assistant/ask` `{question, include_simulated, language}` →
`{answer, mode, intent, entities, tool, data, sources, disclaimers, note}`.

## Procurement
`GET /saved/products`, `PUT|DELETE /saved/products/{id}`, same for `/saved/suppliers`;
`POST /quotes`, `GET /quotes/sent`, `GET /quotes/received`, `GET /quotes/{id}`, `POST /quotes/{id}/responses`,
`POST /quotes/{id}/close`; `GET /notifications`, `POST /notifications/{id}/read`.

## Market data (`market_data.manage`)
`GET|POST /market-data/sources`, `PUT /market-data/sources/{id}`; `GET|POST /market-data/connectors`,
`PUT /market-data/connectors/{id}`, `POST /market-data/connectors/{id}/run`; `GET /market-data/jobs`,
`GET /market-data/jobs/{id}/logs`; `POST /market-data/import` (multipart: file, data_source_id, record_type,
allow_create_products); `GET /market-data/matches`, `POST /market-data/matches/{id}` `{action: accept|assign|reject, product_id}`;
`GET|POST /market-data/observations`, `POST /market-data/observations/{id}/verification?status=`,
`POST /market-data/observations/{id}/outlier?is_outlier=`; `GET /market-data/verification-requests`.

## Admin
Users & roles: `GET /admin/users`, `PATCH /admin/users/{id}`, `GET /admin/roles`, `GET /admin/permissions`,
`PUT /admin/roles/{code}/permissions`, `GET /admin/organizations`.
Configuration: `GET /admin/settings`, `PUT /admin/settings/{key}`, `POST /admin/categories`, `PUT /admin/categories/{id}`,
`POST /admin/categories/{id}/attributes`, `PUT|DELETE /admin/attributes/{id}`, `POST|PUT /admin/units`,
`POST|DELETE /admin/unit-conversions`, `POST|PUT /admin/regions`, `POST /admin/districts`, `POST /admin/exchange-rates`,
`GET /admin/subscription-plans`. Audit: `GET /admin/audit-logs`. Demo: `GET|DELETE /admin/demo-data`.

`GET /api/health` — liveness + DB check.
