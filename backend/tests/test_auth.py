def test_register_buyer_and_me(client):
    r = client.post("/api/auth/register", json={"email": "Buyer@Example.uz", "password": "Secret123", "full_name": "Ali Valiyev",
                                               "account_type": "buyer", "organization_name": "Ali Savdo"})
    assert r.status_code == 201, r.text
    tok = r.json()["access_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    assert me["email"] == "buyer@example.uz"
    assert me["role"] == "buyer"
    assert "quotes.request" in me["permissions"]
    assert me["organizations"][0]["name"] == "Ali Savdo"


def test_register_supplier_creates_unverified_supplier(client, f):
    tash = f.region("UZ-TK")
    r = client.post("/api/auth/register", json={"email": "s@x.uz", "password": "Secret123", "full_name": "Sardor",
                                               "account_type": "supplier", "organization_name": "Sardor Cement",
                                               "region_id": tash.id, "supplier_type": "distributor"})
    assert r.status_code == 201, r.text
    h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    mine = client.get("/api/suppliers/mine", headers=h).json()
    assert len(mine) == 1 and mine[0]["verification_status"] == "unverified"


def test_supplier_registration_requires_region(client):
    r = client.post("/api/auth/register", json={"email": "s2@x.uz", "password": "Secret123", "full_name": "Sardor",
                                               "account_type": "supplier", "organization_name": "Org"})
    assert r.status_code == 422


def test_cannot_self_register_admin(client):
    r = client.post("/api/auth/register", json={"email": "a@x.uz", "password": "Secret123", "full_name": "Hacker",
                                               "account_type": "super_admin", "organization_name": "Org"})
    assert r.status_code == 422


def test_weak_password_rejected(client):
    r = client.post("/api/auth/register", json={"email": "w@x.uz", "password": "password", "full_name": "W W",
                                               "account_type": "buyer", "organization_name": "Org"})
    assert r.status_code == 422


def test_duplicate_email(client):
    body = {"email": "d@x.uz", "password": "Secret123", "full_name": "D D", "account_type": "buyer", "organization_name": "Org"}
    assert client.post("/api/auth/register", json=body).status_code == 201
    assert client.post("/api/auth/register", json=body).status_code == 409


def test_login_wrong_password(client, f):
    u, _ = f.user("buyer")
    assert client.post("/api/auth/login", json={"email": u.email, "password": "wrong"}).status_code == 401


def test_refresh_and_logout_revokes(client, f):
    u, _ = f.user("buyer")
    t = client.post("/api/auth/login", json={"email": u.email, "password": "Passw0rd123"}).json()
    r = client.post("/api/auth/refresh", json={"refresh_token": t["refresh_token"]})
    assert r.status_code == 200
    h = {"Authorization": f"Bearer {t['access_token']}"}
    assert client.post("/api/auth/logout", headers=h).status_code == 204
    assert client.post("/api/auth/refresh", json={"refresh_token": t["refresh_token"]}).status_code == 401


def test_access_token_cannot_be_used_as_refresh(client, f):
    u, _ = f.user("buyer")
    t = client.post("/api/auth/login", json={"email": u.email, "password": "Passw0rd123"}).json()
    assert client.post("/api/auth/refresh", json={"refresh_token": t["access_token"]}).status_code == 401


def test_invalid_token(client):
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/auth/me").status_code == 401


def test_disabled_user_cannot_login(client, f, db):
    u, _ = f.user("buyer")
    u.is_active = False
    db.commit()
    assert client.post("/api/auth/login", json={"email": u.email, "password": "Passw0rd123"}).status_code == 403


def test_bootstrap_admin_default_email_is_valid():
    from pydantic import TypeAdapter, EmailStr
    from app.core.config import Settings
    TypeAdapter(EmailStr).validate_python(Settings.model_fields["bootstrap_admin_email"].default)
