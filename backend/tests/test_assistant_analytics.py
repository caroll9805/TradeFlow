from datetime import timedelta
from decimal import Decimal

from app.models import PriceObservation
from app.models.base import utcnow
from app.seed.demo import seed_demo


def _market(f):
    _, o1, h1 = f.login_as("supplier")
    _, o2, h2 = f.login_as("supplier")
    s1 = f.supplier(o1, "Toshkent Sement", "UZ-TK")
    s2 = f.supplier(o2, "Samarqand Sement", "UZ-SA")
    p = f.product("Portland cement M400 50kg", bag_kg=50, terms=["sement", "цемент"])
    f.offer(h1, s1, p, 76000, unit="bag", available_qty="1000")
    f.offer(h2, s2, p, 71000, unit="bag", available_qty="300")
    return p, s1, s2


def test_assistant_cheapest_english(client, f):
    p, s1, s2 = _market(f)
    r = client.post("/api/assistant/ask", json={"question": "Where can I buy cement at the lowest price in Uzbekistan?"})
    assert r.status_code == 200, r.text
    a = r.json()
    assert a["mode"] == "deterministic" and a["intent"] == "cheapest"
    assert a["entities"]["product"]["id"] == p.id
    assert "Samarqand Sement" in a["answer"] and "1 420" in a["answer"]  # 71000/50
    assert a["data"]["cheapest_offer_id"] is not None
    assert a["sources"] and a["sources"][0]["kind"] == "supplier_declared"


def test_assistant_region_comparison_russian(client, f):
    _market(f)
    a = client.post("/api/assistant/ask", json={"question": "Сравни цены на цемент в Ташкенте и Самарканде"}).json()
    assert a["language"] == "ru" and a["intent"] == "compare_regions"
    assert {r["code"] for r in a["entities"]["regions"]} == {"UZ-TK", "UZ-SA"}
    assert "Самарканд" in a["answer"] and "%" in a["answer"]


def test_assistant_uzbek_suppliers_in_region(client, f):
    _market(f)
    a = client.post("/api/assistant/ask", json={"question": "Toshkentda sementni kim sotadi?"}).json()
    assert a["language"] == "uz" and a["intent"] == "suppliers"
    assert "Toshkent Sement" in a["answer"] and "Samarqand Sement" not in a["answer"]


def test_assistant_min_quantity(client, f):
    _market(f)
    a = client.post("/api/assistant/ask", json={"question": "Find suppliers of cement that can provide at least 20000 kg"}).json()
    assert a["intent"] == "min_quantity"
    assert "Toshkent Sement" in a["answer"]  # 1000 bags = 50000 kg
    assert "• [" not in a["answer"]
    lines = [l for l in a["answer"].splitlines() if l.startswith("•")]
    assert len(lines) == 1  # Samarqand has 300 bags = 15000 kg


def test_assistant_does_not_invent(client, f):
    _market(f)
    a = client.post("/api/assistant/ask", json={"question": "What is the price of unobtainium bars?"}).json()
    assert a["data"] is None and a["sources"] == []
    a = client.post("/api/assistant/ask", json={"question": "Which products have experienced significant price increases?"}).json()
    assert a["intent"] == "price_increases" and "Insufficient data" in a["answer"]


def test_price_history_and_movers(client, f, db):
    p, s1, _ = _market(f)
    src = f.source("admin_manual_entry")
    now = utcnow()
    for d, price in [(25, 1300), (22, 1310), (20, 1320), (6, 1500), (4, 1510), (2, 1520)]:
        db.add(PriceObservation(product_id=p.id, original_price=Decimal(price), original_currency="UZS", unit_id=f.unit("kg").id,
                                price_uzs=Decimal(price), normalized_price_uzs=Decimal(price), normalized_unit_id=f.unit("kg").id,
                                region_id=f.region("UZ-TK").id, price_type="wholesale", provenance_kind="official_statistic",
                                data_source_id=src.id, collection_method="manual", observed_at=now - timedelta(days=d)))
    db.commit()
    h = client.get(f"/api/products/{p.id}/history", params={"granularity": "week", "days": 60}).json()
    assert h["status"] == "ok" and h["points"] and h["change_pct"] > 0
    assert "official_statistic" in h["provenance_breakdown"]
    mv = client.get("/api/analytics/movers").json()
    assert mv["status"] == "ok" and mv["increases"][0]["product_id"] == p.id
    fc = client.get(f"/api/products/{p.id}/forecast").json()
    assert fc["status"] == "insufficient_data" and fc["kind"] == "estimate"


def test_supply_demand_keeps_signals_separate(client, f):
    p, _, _ = _market(f)
    client.get("/api/products", params={"q": "cement"})
    sd = client.get(f"/api/products/{p.id}/supply-demand").json()
    assert sd["observed_supply"]["active_offers"] == 2
    assert sd["completed_transactions"] == "insufficient_data"
    assert sd["estimated_demand"] == "insufficient_data"
    assert Decimal(str(sd["declared_stock_base_units"])) == Decimal(65000)


def test_overview_and_regions(client, f):
    _market(f)
    ov = client.get("/api/analytics/overview").json()
    assert ov["active_offers"] == 2 and ov["products_indexed"] == 1
    regs = client.get("/api/analytics/regions").json()
    tk = next(r for r in regs if r["code"] == "UZ-TK")
    assert tk["active_offers"] == 1 and len(regs) == 14


def test_demo_seed_labelled_and_purgeable(client, f, db, admin):
    _, _, h = admin
    res = seed_demo(db)
    assert res["status"] == "seeded" and res["offers"] > 50
    # every demo offer is simulated and flagged in comparisons
    lst = client.get("/api/offers", params={"page_size": 100}).json()["items"]
    assert lst and all(o["is_simulated"] and o["provenance_kind"] == "simulated" for o in lst)
    assert all(o["supplier"]["verification_status"] != "verified" for o in lst)
    # all 13 categories have demo products
    ov = client.get("/api/analytics/overview").json()
    assert all(c["offers"] > 0 for c in ov["offers_by_category"])
    # real data stays when purging
    _, org, hs = f.login_as("supplier")
    s = f.supplier(org, "Real Supplier", "UZ-TK")
    real = f.product("Real product")
    f.offer(hs, s, real, 100)
    r = client.delete("/api/admin/demo-data", headers=h)
    assert r.status_code == 200
    counts = client.get("/api/admin/demo-data", headers=h).json()
    assert counts["offers"] == 0 and counts["observations"] == 0 and counts["products"] == 0
    assert client.get("/api/offers").json()["total"] == 1


def test_anomaly_detection(client, f, db, admin):
    _, _, h = admin
    p, _, _ = _market(f)
    src = f.source("admin_manual_entry")
    now = utcnow()
    prices = [1500, 1510, 1490, 1505, 1495, 1500, 1502, 4000]
    for i, price in enumerate(prices):
        db.add(PriceObservation(product_id=p.id, original_price=Decimal(price), original_currency="UZS", unit_id=f.unit("kg").id,
                                price_uzs=Decimal(price), normalized_price_uzs=Decimal(price), region_id=f.region("UZ-TK").id,
                                price_type="wholesale", provenance_kind="official_statistic", data_source_id=src.id,
                                collection_method="manual", observed_at=now - timedelta(days=i)))
    db.commit()
    an = client.get("/api/analytics/anomalies", headers=h).json()
    assert an["status"] == "ok"
    assert any(a["price"] == 4000 and a["direction"] == "above" for a in an["anomalies"])


def test_demo_accounts_can_log_in(client, db):
    """Regression: demo e-mails must pass EmailStr validation (special-use TLDs like .local are rejected)."""
    seed_demo(db)
    for role in ("buyer", "supplier", "data", "admin"):
        r = client.post("/api/auth/login", json={"email": f"{role}@demo.example.com", "password": "Demo12345!"})
        assert r.status_code == 200, (role, r.text)
