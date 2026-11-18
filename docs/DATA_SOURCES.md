# Data sources & connector guide

## Principles
* Prefer official APIs and data feeds; then authorised files and supplier submissions; web collection only where the
  site's terms and the law allow it.
* Never bypass authentication, CAPTCHAs, rate limits, paywalls or anti-bot systems. Never invent endpoints.
* Every record keeps provenance (source, URL/record id, method, original name/price/unit/currency, observed and
  collected times, verification status, quality score, match confidence).
* Asking prices ≠ transactions. Official statistics are stored with provenance `official_statistic` and usually
  describe *retail/consumer* prices — label them as such (price_type `retail`).

## Review checklist before enabling a source
Record the answers in *Market data → Data sources* (fields exist for each):
1. Is it reachable and stable? 2. Is there a documented public API or bulk download? 3. Do the terms permit automated
collection? 4. Is the information public? 5. Is authentication required (and are we authorised)? 6. May we store and
redistribute it (attribution/licence)? 7. Wholesale, retail or statistical prices? 8. Update frequency (set
`freshness_hours`)? Only then set `terms_status = permitted`; `http_json` connectors refuse to run otherwise.

## Current status of candidate sources (desk research, 17 Nov 2026 — nothing is integrated)
| Source | What we found | Next step |
|---|---|---|
| **NarxStat** — narx.stat.uz (National Statistics Committee) | Launched 13 Nov 2026 per press reports: CPI, weekly average prices of essential food and fuel by region and district, housing and producer price indices; CSV/JSON downloads and an API without registration. | Most promising first integration. Read the official API documentation, confirm reuse/attribution terms, map product names and region codes, configure an `http_json` connector. |
| narxtahlil.uz (Central Bank) | Reported price-monitoring site based on statistics data (Apr 2026). | Check for downloads/API and terms. |
| B2B Market Uzbekistan — b2bmarket.uz | Commercial B2B marketplace operated by OOO B2BMARKET (Tashkent). No public API found. | Ask for a partner feed or written permission; until then rely on supplier submissions and authorised imports. |
| “Uzxarid” | Likely the UZEX public e-procurement system (xarid.uzex.uz) — to be confirmed. | Tender/contract results are a different price kind; check data rights. |
| UZEX B2B trading — yarmarka.uzex.uz | Exchange B2B trading platform. | Investigate published results and terms. |
| B2B Savdo | Could not confirm the platform. | Locate the official site. |
| Made in Uzbekistan | Name used by several catalogues (e.g. the cooperation.uz domestic-manufacturer portal). | Identify intended source, review terms. |

These rows are seeded as **inactive** data sources with their review notes so the work is tracked in the admin UI.

## Connector types
| Type | Model | Notes |
|---|---|---|
| `supplier_submission` | push | offers from the supplier dashboard/API (`supplier_declared`) |
| `file_import` | upload | CSV (UTF-8, `,`/`;`/tab) or XLSX; headers in en/uz/ru (e.g. `product_name/mahsulot/товар`, `price/narx/цена`, `unit/birlik/ед`, `region/viloyat/регион`) |
| `manual_entry` | push | admin-entered observations with source URL |
| `http_json` | pull/scheduled | config: `url`, `records_path`, `field_map` (TradeFlow field → JSON dot path), `static_fields`, `headers`, `timeout_seconds`; requires `permitted` terms; refuses on 401/403 |

### Adding a new connector
1. Create `backend/app/services/market_data/connectors/<name>.py`, subclass `SourceConnector`, set `type_key`,
   `description`, `config_schema`, `requires_terms_permission`, implement `collect(**kwargs)` returning raw dicts with
   the canonical fields below, decorate with `@register`.
2. Import the module in `services/market_data/__init__.py`.
3. Create the data source + connector in the admin UI; set an interval for the worker.
Validation, matching, normalisation, de-duplication, scoring, storage, job metrics and logs are shared — do not
reimplement them in the connector.

Canonical raw fields: `product_name`*, `price`*, `currency` (default UZS), `unit`, `region` (code or name/alias),
`price_type`, `supplier_name`, `supplier_tin`, `supplier_type`, `brand`, `barcode`, `sku`, `category`, `observed_at`,
`source_url`, `record_type` (`observation`|`offer`), `moq`, `available_qty`, `delivery_available`, `delivery_cost`,
`valid_until`.

## Product matching
barcode (exact, 1.00) → SKU (0.98) → normalised name exact (0.97) → fuzzy (token Jaccard + sequence ratio over name and
synonyms, ± brand agreement). `matching.auto_accept_threshold` (default 0.92) accepts automatically;
anything else is held in the review queue with the raw row; admins accept, assign to another product or reject.
Unknown products are only created automatically when the import explicitly allows it and a category is given.
Normalisation handles Uzbek Latin/Cyrillic and Russian (transliteration, apostrophes, `50 kg` → `50kg`).
