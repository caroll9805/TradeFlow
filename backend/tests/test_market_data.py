import io
from decimal import Decimal

import httpx
import pytest
from openpyxl import Workbook
from sqlalchemy import select

from app.models import DataConnector, PriceObservation, ProductMatch
from app.services.market_data.base import ConnectorError
from app.services.market_data.connectors.http_json import HttpJsonConnector
from app.services.market_data.pipeline import run_collection

CSV = """product_name,price,currency,unit,region,price_type,supplier,observed_at,source_url
Portland cement M400 50kg,75000,UZS,qop,Toshkent shahri,wholesale,Alpha Build,2026-10-01,https://example.uz/p/1
Portland cement M400 50kg,75000,UZS,qop,Toshkent shahri,wholesale,Alpha Build,2026-10-01,https://example.uz/p/1
Portland cement M400 50kg,1450,UZS,кг,Самарканд,wholesale,Beta Trade,2026-10-02,
Cement portland M-400 meshok,76000,UZS,мешок,Buxoro,wholesale,Gamma,2026-10-02,
Unknown widget 3000,5000,UZS,dona,Toshkent,retail,,2026-10-03,
Portland cement M400 50kg,abc,UZS,kg,Toshkent,wholesale,,2026-10-03,
Portland cement M400 50kg,1500,UZS,parsec,Toshkent,wholesale,,2026-10-03,
Portland cement M400 50kg,1500,UZS,kg,Moscow,wholesale,,2026-10-03,
Portland cement M400 50kg,1500,EUR,kg,Toshkent,wholesale,,2026-10-03,
"""


def test_csv_import_pipeline(client, f, db, admin):
    _, _, h = admin
    p = f.product("Portland cement M400 50kg", bag_kg=50)
    src = f.source("authorized_file_imports")
    r = client.post("/api/market-data/import", headers=h, data={"data_source_id": str(src.id)},
                    files={"file": ("prices.csv", CSV.encode(), "text/csv")})
    assert r.status_code == 200, r.text
    job = r.json()
    assert job["records_seen"] == 9
    assert job["records_collected"] == 2  # rows 1 and 3
    assert job["records_duplicate"] == 1  # row 2
    assert job["records_pending_review"] == 2  # fuzzy match + unknown product
    assert job["records_rejected"] == 4  # bad price, unit, region, missing EUR rate
    assert job["status"] == "partial"
    obs = db.scalars(select(PriceObservation).where(PriceObservation.product_id == p.id).order_by(PriceObservation.id)).all()
    assert len(obs) == 2
    o1 = obs[0]
    # provenance is complete
    assert o1.original_product_name == "Portland cement M400 50kg" and o1.original_unit_text == "qop"
    assert o1.source_url == "https://example.uz/p/1" and o1.collection_method == "file_import"
    assert o1.provenance_kind == "supplier_declared" and o1.collection_job_id == job["id"]
    assert Decimal(o1.normalized_price_uzs) == Decimal("1500")
    assert o1.supplier_id is not None and o1.is_simulated is False
    logs = client.get(f"/api/market-data/jobs/{job['id']}/logs", headers=h).json()
    msgs = " ".join(l["message"] for l in logs)
    assert "Unknown unit" in msgs and "region" in msgs and "exchange rate" in msgs
    # uncertain matches are held for review, never auto-merged
    pending = client.get("/api/market-data/matches", headers=h).json()["items"]
    assert len(pending) == 2
    fuzzy = next(m for m in pending if m["original_name"].startswith("Cement portland"))
    r = client.post(f"/api/market-data/matches/{fuzzy['id']}", json={"action": "accept"}, headers=h)
    assert r.status_code == 200 and r.json()["ingest_result"] == "stored"
    assert len(db.scalars(select(PriceObservation).where(PriceObservation.product_id == p.id)).all()) == 3
    unknown = next(m for m in pending if m["original_name"].startswith("Unknown"))
    assert client.post(f"/api/market-data/matches/{unknown['id']}", json={"action": "reject"}, headers=h).json()["status"] == "rejected"


def test_xlsx_import_offers(client, f, db, admin):
    _, _, h = admin
    p = f.product("Granulated sugar 50kg", cat="food", bag_kg=50)
    wb = Workbook()
    ws = wb.active
    ws.append(["Mahsulot", "Narx", "Birlik", "Viloyat", "Yetkazib_beruvchi", "moq", "qoldiq"])
    ws.append(["Granulated sugar 50kg", 640000, "qop", "Andijon", "Sweet LLC", 10, 400])
    buf = io.BytesIO()
    wb.save(buf)
    src = f.source("authorized_file_imports")
    r = client.post("/api/market-data/import", headers=h,
                    data={"data_source_id": str(src.id), "record_type": "offer"},
                    files={"file": ("list.xlsx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    assert r.json()["records_collected"] == 1
    comp = client.get(f"/api/products/{p.id}/compare").json()
    o = comp["offers"][0]
    assert o["supplier"]["name"] == "Sweet LLC" and o["supplier"]["verification_status"] == "unverified"
    assert Decimal(o["price"]["per_base_unit_uzs"]) == Decimal("12800")
    assert o["provenance"]["source"] == src.name


def test_import_rejects_bad_files(client, f, admin):
    _, _, h = admin
    src = f.source("authorized_file_imports")
    r = client.post("/api/market-data/import", headers=h, data={"data_source_id": str(src.id)},
                    files={"file": ("x.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 415
    r = client.post("/api/market-data/import", headers=h, data={"data_source_id": str(src.id)},
                    files={"file": ("x.xlsx", b"not a zip", "application/octet-stream")})
    assert r.status_code == 415
    r = client.post("/api/market-data/import", headers=h, data={"data_source_id": str(src.id)},
                    files={"file": ("x.csv", b"foo,bar\n1,2\n", "text/csv")})
    assert r.status_code == 200 and r.json()["status"] == "failed"


def test_http_connector_blocked_until_terms_permitted(db, f):
    src = f.source("cand_narxstat")
    conn = DataConnector(data_source_id=src.id, name="t", connector_type="http_json",
                         config={"url": "https://example.org/data.json", "field_map": {"product_name": "n", "price": "p"}})
    db.add(conn)
    db.commit()
    with pytest.raises(ConnectorError):
        list(HttpJsonConnector(conn, src).collect())
    job = run_collection(db, source=src, connector=conn, user=None)
    assert job.status == "failed" and "terms" in job.error
    assert conn.last_failure_at is not None and conn.last_error


def test_http_connector_with_permitted_source(db, f):
    p = f.product("Granulated sugar 50kg", cat="food", bag_kg=50)
    src = f.source("cand_narxstat")
    src.terms_status = "permitted"
    db.commit()
    payload = {"data": {"items": [{"name": "Granulated sugar 50kg", "price": 12900, "unit": "kg", "region": "UZ-TK"},
                                  {"name": "Granulated sugar 50kg", "price": "bad", "unit": "kg", "region": "UZ-TK"}]}}
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json=payload))
    conn = DataConnector(data_source_id=src.id, name="t", connector_type="http_json",
                         config={"url": "https://example.org/data.json", "records_path": "data.items",
                                 "field_map": {"product_name": "name", "price": "price", "unit": "unit", "region": "region"},
                                 "static_fields": {"price_type": "retail"}})
    db.add(conn)
    db.commit()
    recs = list(HttpJsonConnector(conn, src).collect(client=httpx.Client(transport=transport)))
    assert recs[0]["product_name"] == "Granulated sugar 50kg" and recs[0]["price_type"] == "retail"
    # connector refuses (does not bypass) access-denied responses
    deny = httpx.MockTransport(lambda req: httpx.Response(403))
    with pytest.raises(ConnectorError):
        HttpJsonConnector(conn, src).collect(client=httpx.Client(transport=deny))
    assert p.id


def test_manual_observation_and_verification(client, f, admin, db):
    _, _, h = admin
    p = f.product("Onion", cat="agriculture")
    src = f.source("admin_manual_entry")
    r = client.post("/api/market-data/observations", headers=h, json={
        "product_id": p.id, "price": "3200", "unit_id": f.unit("kg").id, "region_id": f.region("UZ-NG").id,
        "data_source_id": src.id, "observed_at": "2026-10-10T00:00:00Z", "price_type": "retail",
        "source_url": "https://stat.example.uz/bulletin"})
    assert r.status_code == 201, r.text
    oid = r.json()["id"]
    assert r.json()["provenance_kind"] == "official_statistic"
    r = client.post(f"/api/market-data/observations/{oid}/verification", params={"status": "verified"}, headers=h)
    assert r.json()["verification_status"] == "verified"
    r = client.post("/api/market-data/observations", headers=h, json={
        "product_id": p.id, "price": "3200", "unit_id": f.unit("kg").id, "region_id": f.region("UZ-NG").id,
        "data_source_id": src.id, "observed_at": "2099-01-01T00:00:00Z"})
    assert r.status_code == 422
    assert db.scalar(select(ProductMatch)) is None
