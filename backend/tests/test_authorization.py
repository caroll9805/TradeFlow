from decimal import Decimal


def test_buyer_cannot_manage_catalog(client, f):
    _, _, h = f.login_as("buyer")
    r = client.post("/api/admin/categories", json={"slug": "x-cat", "name_uz": "X", "name_ru": "X"}, headers=h)
    assert r.status_code == 403
    assert client.get("/api/admin/users", headers=h).status_code == 403
    assert client.get("/api/market-data/sources", headers=h).status_code == 403


def test_anonymous_cannot_write(client, f):
    assert client.post("/api/offers", json={}).status_code in (401, 422)
    assert client.get("/api/saved/products").status_code == 401


def test_supplier_cannot_edit_other_suppliers_offer(client, f):
    u1, org1, h1 = f.login_as("supplier")
    u2, org2, h2 = f.login_as("supplier")
    s1 = f.supplier(org1, "S1", "UZ-TK")
    f.supplier(org2, "S2", "UZ-SA")
    p = f.product("Cement M400", bag_kg=50)
    o = f.offer(h1, s1, p, 1500)
    # supplier 2 cannot modify supplier 1's offer or publish on its behalf
    assert client.patch(f"/api/offers/{o['id']}", json={"price": "1"}, headers=h2).status_code == 403
    assert client.delete(f"/api/offers/{o['id']}", headers=h2).status_code == 403
    r = client.post("/api/offers", json={"supplier_id": s1.id, "product_id": p.id, "price": "1", "unit_id": f.unit("kg").id,
                                         "region_id": f.region("UZ-TK").id}, headers=h2)
    assert r.status_code == 403
    # and cannot edit supplier 1's profile
    r = client.put(f"/api/suppliers/{s1.id}", json={"name": "hijack", "supplier_type": "other", "region_id": f.region("UZ-TK").id}, headers=h2)
    assert r.status_code == 403


def test_supplier_cannot_self_verify(client, f):
    _, org, h = f.login_as("supplier")
    s = f.supplier(org, "S", "UZ-TK")
    r = client.post(f"/api/suppliers/{s.id}/verification", json={"status": "verified"}, headers=h)
    assert r.status_code == 403


def test_admin_verifies_supplier_and_audit_logged(client, f, admin):
    _, _, ha = admin
    _, org, hs = f.login_as("supplier")
    s = f.supplier(org, "S", "UZ-TK")
    assert client.post(f"/api/suppliers/{s.id}/verification-request", headers=hs).status_code == 201
    r = client.post(f"/api/suppliers/{s.id}/verification", json={"status": "verified", "notes": "Docs checked"}, headers=ha)
    assert r.status_code == 200 and r.json()["verification_status"] == "verified"
    logs = client.get("/api/admin/audit-logs?entity_type=supplier", headers=ha).json()["items"]
    assert any(l["action"] == "verification" for l in logs)


def test_quote_isolation_between_organizations(client, f):
    _, sorg, hs = f.login_as("supplier")
    _, _, hb1 = f.login_as("buyer")
    _, _, hb2 = f.login_as("buyer")
    s = f.supplier(sorg, "S", "UZ-TK")
    p = f.product("Cement", bag_kg=50)
    r = client.post("/api/quotes", json={"product_id": p.id, "supplier_id": s.id, "quantity": "10", "unit_id": f.unit("bag").id},
                    headers=hb1)
    assert r.status_code == 201
    qid = r.json()["id"]
    assert client.get(f"/api/quotes/{qid}", headers=hb1).status_code == 200
    assert client.get(f"/api/quotes/{qid}", headers=hb2).status_code == 404  # other buyer org
    assert client.get("/api/quotes/sent", headers=hb2).json() == []
    # supplier sees and answers it
    rec = client.get("/api/quotes/received", headers=hs).json()
    assert [q["id"] for q in rec] == [qid]
    r = client.post(f"/api/quotes/{qid}/responses", json={"price": "70000", "unit_id": f.unit("bag").id}, headers=hs)
    assert r.status_code == 201 and r.json()["status"] == "answered"
    # buyer 2 can't respond as supplier (lacks permission)
    assert client.post(f"/api/quotes/{qid}/responses", json={"price": "1", "unit_id": f.unit("bag").id}, headers=hb2).status_code == 403


def test_role_change_requires_users_manage(client, f, admin):
    _, _, ha = admin
    u, _, hb = f.login_as("buyer")
    assert client.patch(f"/api/admin/users/{u.id}", json={"role_code": "super_admin"}, headers=hb).status_code == 403
    r = client.patch(f"/api/admin/users/{u.id}", json={"role_code": "supplier"}, headers=ha)
    assert r.status_code == 200 and r.json()["role"] == "supplier"


def test_rating_requires_org_and_updates_average(client, f):
    _, sorg, _ = f.login_as("supplier")
    s = f.supplier(sorg, "S", "UZ-TK")
    _, _, hb = f.login_as("buyer")
    r = client.post(f"/api/suppliers/{s.id}/ratings", json={"score": 4}, headers=hb)
    assert r.status_code == 201 and Decimal(str(r.json()["rating_avg"])) == Decimal("4")
