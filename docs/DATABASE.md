# Database schema

PostgreSQL 16 (+ PostGIS extension enabled by the baseline migration). Money: `NUMERIC(20,2)`; normalised unit prices
`NUMERIC(24,6)`; quantities `NUMERIC(20,4)`; rates `NUMERIC(20,6)`. All timestamps are `timestamptz` (UTC stored,
shown in Asia/Tashkent). Source of truth: `backend/app/models/*.py`. Migrations: `backend/alembic/`.

## Identity & access
| Table | Purpose / key columns |
|---|---|
| `users` | email (unique), password_hash (bcrypt), full_name, phone, role_id → roles, is_active, locale, token_version (refresh revocation), last_login_at |
| `roles` | code (buyer, supplier, manufacturer, market_data_admin, super_admin), names uz/ru/en, is_self_registrable |
| `permissions` | code (e.g. `catalog.manage`, `market_data.manage`, `quotes.request`) |
| `role_permissions` | role ↔ permission (editable in admin) |
| `organizations` | name, org_type (buyer/supplier/manufacturer/platform), tin, region_id, subscription_plan_id, is_simulated |
| `organization_members` | organization ↔ user, member_role — basis of data isolation |
| `subscription_plans` | code, audience, features (JSON) — monetization-ready, no billing |

## Reference & configuration
| Table | Purpose |
|---|---|
| `regions` | 14 regions: code (ISO 3166-2:UZ style), names uz/ru/en, aliases (JSON), approximate centre lat/lng |
| `districts` | region_id, names (Tashkent city districts seeded) |
| `units` | code, names, symbol, dimension (mass/volume/length/area/count/package), factor_to_base, aliases |
| `unit_conversions` | product-specific conversions (product_id, from_unit, to_unit, factor) |
| `categories` | slug, names, parent_id, keywords, is_active, compliance note, freshness_hours |
| `category_attributes` | category_id, code, names, data_type, unit_id, is_required, is_filterable, is_matching_key |
| `attribute_options` | options for select/multiselect attributes |
| `exchange_rates` | currency, rate_to_uzs, as_of, source |
| `platform_settings` | key → JSON value (ranking weights, thresholds, analytics parameters) |

## Catalog & suppliers
| Table | Purpose |
|---|---|
| `manufacturers` | name, country_code, organization_id, is_simulated |
| `products` | name, normalized_name (search/matching), search_terms (JSON synonyms), category_id, brand, model, manufacturer_id, sku, barcode, base_unit_id, country_of_origin, origin_type, status, is_simulated |
| `product_attributes` | product_id, attribute_id, value_text / value_number / value_bool / value_json (unique per product+attribute) |
| `product_images` | product_id, url, sort_order |
| `suppliers` | organization_id, name, legal_name, tin, supplier_type, contacts, social_links, region/district, address, verification_status (+ verified_at/by), rating_avg/count, data_source_id, is_active, is_simulated |
| `supplier_categories` | supplier ↔ category |
| `supplier_locations` | supplier_id, kind, region/district, address, lat/lng (only when provided) |

## Market data
| Table | Purpose |
|---|---|
| `data_sources` | code, name, source_type, default_provenance, base_url, terms_status (unknown/pending_review/permitted/not_permitted), has_public_api, requires_auth, redistribution_allowed, price_kind, review_notes, reliability_score, freshness_hours, is_active, is_simulated |
| `data_connectors` | data_source_id, connector_type (registry key), config (JSON), interval_minutes, is_enabled, last_run/success/failure, last_error, totals |
| `collection_jobs` | connector/source, trigger, status, timings, counters (seen, collected, rejected, pending_review, duplicate), error, file_name |
| `collection_logs` | job_id, level, row_number, message, payload |
| `offers` | **current** offer: supplier, product, original_price/currency, unit, exchange_rate (+at), price_uzs, price_per_base_unit_uzs, units_per_offer_unit, moq, available_qty, region/district/location, delivery (available, cost, regions), other fees, validity, price_type, verification_status, provenance_kind, data_source_id, source_url, original_product_name, is_active, is_simulated, is_featured, price_updated_at |
| `price_observations` | **append-only history**: product, supplier, offer, original name/price/currency/unit text, unit, exchange_rate, price_uzs, normalized_price_uzs + unit, region, price_type, provenance_kind, data_source, collection_job, collection_method, source_url/record_id, observed_at, collected_at, verification_status, quality_score, confidence, quality_flags, is_outlier, is_simulated |
| `product_matches` | uncertain matches held for review: original_name, candidate_product_id, score, method, reasons, status, raw_record |

Provenance kinds: `supplier_declared`, `marketplace_listed`, `official_statistic`, `verified_transaction`,
`estimated`, `simulated`.

## Procurement & activity
| Table | Purpose |
|---|---|
| `quote_requests` / `quote_responses` | RFQ-lite between a buyer organization and a supplier |
| `saved_products` / `saved_suppliers` | per-user bookmarks |
| `supplier_ratings` | one rating per (supplier, organization) |
| `verification_requests` | supplier verification queue with evidence and reviewer notes |
| `search_events` | search/view interest signal (never reported as demand) |
| `notifications` | per-user notifications (quote requests/responses) |
| `audit_logs` | user, action, entity, changes (JSON), ip, time |

## Indexes (highlights)
`products(normalized_name)`, `products(barcode)`, `products(category_id)`, `offers(product_id, is_active)`,
`offers(region_id)`, `price_observations(product_id, observed_at)`, `price_observations(region_id, observed_at)`,
`price_observations(provenance_kind)`, `suppliers(region_id)`, `suppliers(verification_status)`,
`search_events(created_at)`, `audit_logs(created_at)`, plus every `is_simulated` flag.

## Migrations
`0001_baseline` creates the schema from the ORM metadata and enables PostGIS. Every later change must be an Alembic
revision: `docker compose run --rm backend alembic revision --autogenerate -m "describe change"`, review the generated
file, then `alembic upgrade head`.
