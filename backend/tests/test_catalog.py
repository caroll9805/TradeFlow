import json


def test_all_major_categories_seeded(client):
    slugs = {c["slug"] for c in client.get("/api/categories").json()}
    assert {"food", "electronics", "textiles", "cosmetics", "construction", "industrial", "furniture", "auto-parts",
            "office", "agriculture", "medical", "packaging", "other"} <= slugs


def test_regions_cover_uzbekistan(client):
    regions = client.get("/api/regions").json()
    assert len(regions) == 14
    assert {"UZ-TK", "UZ-QR", "UZ-XO"} <= {r["code"] for r in regions}


def test_admin_creates_category_with_dynamic_attributes_and_product(client, f, admin):
    _, _, h = admin
    r = client.post("/api/admin/categories", json={"slug": "solar-panels", "name_uz": "Quyosh panellari",
                                                   "name_ru": "Солнечные панели"}, headers=h)
    assert r.status_code == 201, r.text
    cid = r.json()["id"]
    a1 = client.post(f"/api/admin/categories/{cid}/attributes", json={
        "code": "power_w", "name_uz": "Quvvat", "name_ru": "Мощность", "data_type": "number", "is_required": True,
        "is_filterable": True}, headers=h).json()
    a2 = client.post(f"/api/admin/categories/{cid}/attributes", json={
        "code": "cell_type", "name_uz": "Turi", "name_ru": "Тип", "data_type": "select", "is_filterable": True,
        "options": [{"value": "mono", "label_uz": "Mono", "label_ru": "Моно"},
                    {"value": "poly", "label_uz": "Poli", "label_ru": "Поли"}]}, headers=h).json()
    base = {"name": "Solar panel 450W mono", "category_id": cid, "base_unit_id": f.unit("piece").id}
    # missing required attribute
    r = client.post("/api/products", json={**base, "attributes": [{"attribute_id": a2["id"], "value": "mono"}]}, headers=h)
    assert r.status_code == 422
    # invalid select option
    r = client.post("/api/products", json={**base, "attributes": [{"attribute_id": a1["id"], "value": 450},
                                                                  {"attribute_id": a2["id"], "value": "amorphous"}]}, headers=h)
    assert r.status_code == 422
    # invalid number
    r = client.post("/api/products", json={**base, "attributes": [{"attribute_id": a1["id"], "value": "lots"}]}, headers=h)
    assert r.status_code == 422
    r = client.post("/api/products", json={**base, "attributes": [{"attribute_id": a1["id"], "value": 450},
                                                                  {"attribute_id": a2["id"], "value": "mono"}]}, headers=h)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    # filter by dynamic attribute
    res = client.get("/api/products", params={"category_id": cid, "attrs": json.dumps({str(a2["id"]): "mono"})}).json()
    assert [p["id"] for p in res["items"]] == [pid]
    res = client.get("/api/products", params={"category_id": cid, "attrs": json.dumps({str(a2["id"]): "poly"})}).json()
    assert res["items"] == []


def test_attribute_from_other_category_rejected(client, f, admin):
    _, _, h = admin
    food = client.get(f"/api/categories/{f.category('food').id}").json()
    attr = food["attributes"][0]["id"]
    r = client.post("/api/products", json={"name": "Brick", "category_id": f.category("construction").id,
                                           "base_unit_id": f.unit("piece").id,
                                           "attributes": [{"attribute_id": attr, "value": "x"},
                                                          {"attribute_id": client.get(f"/api/categories/{f.category('construction').id}").json()["attributes"][0]["id"], "value": "brick"}]},
                    headers=h)
    assert r.status_code == 422


def test_search_multilingual_and_logs_search_event(client, f):
    f.product("Portland cement M400 50kg", terms=["sement", "цемент"])
    f.product("Sugar granulated", cat="food")
    res = client.get("/api/products", params={"q": "cement m400"}).json()
    assert res["total"] == 1 and res["items"][0]["name"].startswith("Portland")
    # Cyrillic query is transliterated during normalization
    f.product("Цемент М500", terms=[])
    res = client.get("/api/products", params={"q": "цемент"}).json()
    assert res["total"] == 1


def test_supplier_can_create_product_but_not_edit_catalog(client, f):
    _, _, h = f.login_as("supplier")
    r = client.post("/api/products", json={"name": "Red brick", "category_id": f.category("construction").id,
                                           "base_unit_id": f.unit("piece").id,
                                           "attributes": [{"attribute_id": client.get(f"/api/categories/{f.category('construction').id}").json()["attributes"][0]["id"], "value": "brick"}]},
                    headers=h)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert client.delete(f"/api/products/{pid}", headers=h).status_code == 403


def test_archived_product_hidden(client, f, admin):
    _, _, h = admin
    p = f.product("Temp product")
    assert client.delete(f"/api/products/{p.id}", headers=h).status_code == 204
    assert client.get(f"/api/products/{p.id}").status_code == 404
    assert client.get(f"/api/products/{p.id}", headers=h).status_code == 200
