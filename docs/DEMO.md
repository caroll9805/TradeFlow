# Hackathon demo script (≈7 minutes)

Prerequisite: `SEED_DEMO=true docker compose up --build`, open <http://localhost:8080>.
Say up front: *“The market numbers you will see are a SIMULATED demo dataset — every such record is flagged and
labelled, and can be purged in one click. The engine, calculations and provenance are real.”*

1. **Landing → Log in** as `buyer@demo.example.com` / `Demo12345!`. Point at the red simulated-data banner.
2. **Dashboard** — KPIs, offers in all 13 categories, price movers, data-source freshness table. Filter by a category
   and region.
3. **Catalog** — pick *Construction materials*, search `cement` (also try `цемент`, `sement`). Open filters: dynamic
   attributes (grade, material type) come from the category definition in the DB.
4. **Product: Portland cement M400** — *Compare offers*: show **Cheapest** vs **Best overall** and the weights.
   Enter quantity `10000` kg and *Deliver to: Toshkent shahri* → totals include MOQ, declared delivery and fees;
   offers without delivery or with unknown delivery cost are flagged and not eligible. Expand a row: score breakdown
   and provenance (source, original name, collected time).
5. Same page: **regional prices**, **price history** (switch day/week/month, region), toggle *Show estimate* (labelled
   estimate or “insufficient data”), **supply & activity indicators** (“Insufficient data” for demand — not invented),
   **observations** table (data provenance).
6. **Request quote** from a supplier → *Procurement* shows it. Log in as `supplier@…` → *Supplier dashboard → Quote
   requests → Respond*; edit an offer price → a new history record appears.
7. **AI assistant** — ask:
   * “Where can I buy cement at the lowest price in Uzbekistan?”
   * “Сравни цены на цемент в Ташкенте и Самарканде”
   * “Toshkentda shakarni ulgurji kim sotadi?”
   * “Which products have experienced significant price increases?”
   Show sources, disclaimers and the *Open comparison* link. Mention LLM mode via `LLM_PROVIDER`.
8. **Regional analytics** — map of 14 regions by offers / suppliers / product price (markers at regional centres only).
9. Log in as `data@…` → **Market data**: sources with legal-review status (NarxStat etc. not yet enabled), connectors
   with health, **import** `sample_data/sample_price_list.csv`, show the job log and the **matching review** queue,
   verification queue (verify a supplier → badge changes everywhere).
10. Log in as `admin@…` → **Platform admin**: create a new category and attribute live, change ranking weights and
    re-open the comparison, audit log, and finally **Demo data → Remove all simulated data**.
