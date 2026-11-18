from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select

from app.models import Offer, PriceObservation


def _setup(f, client):
    _, org1, h1 = f.login_as("supplier")
    _, org2, h2 = f.login_as("supplier")
    _, org3, h3 = f.login_as("supplier")
    cheap = f.supplier(org1, "Cheap Unverified", "UZ-SU", verification="unverified")
    solid = f.supplier(org2, "Solid Verified", "UZ-TK", verification="verified", rating=Decimal("4.8"))
    sam = f.supplier(org3, "Samarkand Trade", "UZ-SA")
    p = f.product("Portland cement M400 50kg", bag_kg=50)
    return p, (cheap, h1), (solid, h2), (sam, h3)


def test_offer_normalization_and_history(client, f, db):
    p, (cheap, h1), _, _ = _setup(f, client)
    o = f.offer(h1, cheap, p, 75000, unit="bag", moq="10", available_qty="500")
    assert Decimal(o["price_per_base_unit_uzs"]) == Decimal("1500")  # 75000 / 50 kg
    assert o["provenance_kind"] == "supplier_declared" and o["verification_status"] == "unverified"
    # update price twice -> history keeps all observations (never overwritten)
    for price in ("76000", "78000"):
        r = client.patch(f"/api/offers/{o['id']}", json={"price": price}, headers=h1)
        assert r.status_code == 200
    obs = db.scalars(select(PriceObservation).where(PriceObservation.offer_id == o["id"]).order_by(PriceObservation.id)).all()
    assert [int(x.original_price) for x in obs] == [75000, 76000, 78000]
    assert all(x.data_source_id == obs[0].data_source_id for x in obs)
    # non-price edits don't create observations
    client.patch(f"/api/offers/{o['id']}", json={"available_qty": "100"}, headers=h1)
    assert len(db.scalars(select(PriceObservation).where(PriceObservation.offer_id == o["id"])).all()) == 3


def test_incompatible_offer_unit_rejected(client, f):
    p, (cheap, h1), _, _ = _setup(f, client)
    r = client.post("/api/offers", json={"supplier_id": cheap.id, "product_id": p.id, "price": "100",
                                         "unit_id": f.unit("l").id, "region_id": cheap.region_id}, headers=h1)
    assert r.status_code == 422


def test_foreign_currency_requires_recorded_rate(client, f, admin):
    p, (cheap, h1), _, _ = _setup(f, client)
    body = {"supplier_id": cheap.id, "product_id": p.id, "price": "6", "currency": "USD", "unit_id": f.unit("bag").id,
            "region_id": cheap.region_id}
    r = client.post("/api/offers", json=body, headers=h1)
    assert r.status_code == 422 and "exchange rate" in r.text
    _, _, ha = admin
    r = client.post("/api/admin/exchange-rates", json={"currency": "USD", "rate_to_uzs": "12500",
                                                       "as_of": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
                                                       "source": "test rate"}, headers=ha)
    assert r.status_code == 201
    o = client.post("/api/offers", json=body, headers=h1).json()
    assert o["original_currency"] == "USD" and Decimal(o["original_price"]) == 6  # original preserved
    assert Decimal(o["exchange_rate"]) == 12500 and Decimal(o["price_uzs"]) == 75000
    assert Decimal(o["price_per_base_unit_uzs"]) == 1500


def test_cheapest_vs_best_overall(client, f):
    p, (cheap, h1), (solid, h2), (sam, h3) = _setup(f, client)
    f.offer(h1, cheap, p, 70000, unit="bag", available_qty="5", moq="1")  # cheapest, tiny stock, far away
    f.offer(h2, solid, p, 74000, unit="bag", available_qty="1000", moq="1", delivery_available=True, delivery_cost_uzs="100000")
    f.offer(h3, sam, p, 80000, unit="bag", available_qty="1000")
    tk = f.region("UZ-TK")
    res = client.get(f"/api/products/{p.id}/compare", params={"quantity": 5000, "buyer_region_id": tk.id}).json()
    by = {o["supplier"]["name"]: o for o in res["offers"]}
    # 5000 kg = 100 bags. Cheap has only 5 bags -> insufficient stock, not eligible for best.
    assert by["Cheap Unverified"]["stock_status"] == "insufficient"
    assert by["Cheap Unverified"]["eligible_for_best"] is False
    assert res["cheapest_offer_id"] == by["Cheap Unverified"]["offer_id"]
    assert res["best_offer_id"] == by["Solid Verified"]["offer_id"]
    solid_cost = by["Solid Verified"]["cost"]
    assert Decimal(solid_cost["goods_uzs"]) == Decimal("7400000.00")
    assert Decimal(solid_cost["delivery_uzs"]) == Decimal("100000")
    assert Decimal(solid_cost["total_uzs"]) == Decimal("7500000.00")
    assert Decimal(solid_cost["effective_per_base_unit_uzs"]) == Decimal("1500")
    # Samarkand supplier doesn't deliver to Tashkent -> flagged
    assert "no_delivery_to_buyer_region" in by["Samarkand Trade"]["notes"]
    # transparent criteria
    crit = {b["criterion"] for b in by["Solid Verified"]["score_breakdown"]}
    assert crit == {"price", "reliability", "freshness", "stock", "distance"}
    assert res["explanation"]


def test_moq_applied_to_total(client, f):
    p, (cheap, h1), _, _ = _setup(f, client)
    f.offer(h1, cheap, p, 1500, unit="kg", moq="2000")
    res = client.get(f"/api/products/{p.id}/compare", params={"quantity": 500}).json()
    o = res["offers"][0]
    assert Decimal(o["cost"]["order_units"]) == 2000 and "moq_applied" in o["notes"]
    assert Decimal(o["cost"]["total_uzs"]) == Decimal("3000000.00")


def test_unknown_delivery_cost_is_flagged_not_invented(client, f):
    p, (cheap, h1), _, _ = _setup(f, client)
    f.offer(h1, cheap, p, 1500, unit="kg", delivery_available=True)  # cost unknown
    res = client.get(f"/api/products/{p.id}/compare", params={"quantity": 100, "buyer_region_id": f.region("UZ-TK").id}).json()
    o = res["offers"][0]
    assert "delivery_cost_unknown" in o["notes"] and o["cost"]["delivery_uzs"] is None
    assert o["eligible_for_best"] is False


def test_regional_filter_and_regional_prices(client, f):
    p, (cheap, h1), (solid, h2), (sam, h3) = _setup(f, client)
    f.offer(h1, cheap, p, 1400, unit="kg")
    f.offer(h2, solid, p, 1500, unit="kg")
    f.offer(h3, sam, p, 1600, unit="kg")
    res = client.get(f"/api/products/{p.id}/compare", params={"region_id": f.region("UZ-SA").id}).json()
    assert [o["supplier"]["name"] for o in res["offers"]] == ["Samarkand Trade"]
    reg = client.get(f"/api/products/{p.id}/regional").json()
    assert [r["code"] for r in reg] == ["UZ-SU", "UZ-TK", "UZ-SA"]  # sorted by avg price
    lst = client.get("/api/products", params={"region_id": f.region("UZ-TK").id}).json()
    assert lst["total"] == 1 and lst["items"][0]["offer_stats"]["offers"] == 1


def test_expired_offer_excluded(client, f, db):
    p, (cheap, h1), _, _ = _setup(f, client)
    o = f.offer(h1, cheap, p, 1500, unit="kg")
    off = db.get(Offer, o["id"])
    off.valid_until = datetime.now(timezone.utc) - timedelta(days=1)
    db.commit()
    res = client.get(f"/api/products/{p.id}/compare").json()
    assert res["offers"][0]["excluded_reason"] == "offer_expired"
    assert res["cheapest_offer_id"] is None


def test_offer_validation(client, f):
    p, (cheap, h1), _, _ = _setup(f, client)
    base = {"supplier_id": cheap.id, "product_id": p.id, "unit_id": f.unit("kg").id, "region_id": cheap.region_id}
    assert client.post("/api/offers", json={**base, "price": "-5"}, headers=h1).status_code == 422
    assert client.post("/api/offers", json={**base, "price": "5", "currency": "usd"}, headers=h1).status_code == 422
    assert client.post("/api/offers", json={**base, "price": "5", "price_type": "bogus"}, headers=h1).status_code == 422
    assert client.post("/api/offers", json={**base, "price": "5", "moq": "-1"}, headers=h1).status_code == 422
