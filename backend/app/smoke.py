"""End-to-end smoke test against a running stack.

Run inside Docker (goes browser-path: Nginx frontend -> /api proxy -> FastAPI -> PostgreSQL):
    docker compose exec backend python -m app.smoke --base http://frontend
Exit code 0 = every check passed; 1 = at least one failed. Nothing is assumed: each line is a real HTTP call."""
import argparse
import sys
import time
import uuid

import httpx

results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, info: str = "") -> bool:
    results.append((name, ok, info))
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{' — ' + info if info else ''}", flush=True)
    return ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://frontend", help="Base URL that serves the SPA and proxies /api")
    ap.add_argument("--wait", type=int, default=120, help="Seconds to wait for the stack")
    a = ap.parse_args()
    c = httpx.Client(base_url=a.base, timeout=30)

    deadline = time.time() + a.wait
    while True:
        try:
            r = c.get("/api/health")
            if r.status_code == 200:
                break
        except httpx.HTTPError:
            pass
        if time.time() > deadline:
            check("API reachable through frontend proxy", False, f"no healthy response from {a.base}/api/health")
            return 1
        time.sleep(3)
    check("API reachable through frontend proxy (/api/health)", r.json().get("database") == "ok", str(r.json()))

    r = c.get("/")
    check("Frontend serves the SPA (index.html)", r.status_code == 200 and '<div id="root">' in r.text, f"HTTP {r.status_code}")
    r = c.get("/catalog")
    check("SPA deep link falls back to index.html", r.status_code == 200 and '<div id="root">' in r.text, f"HTTP {r.status_code}")

    regions = c.get("/api/regions").json()
    check("14 regions seeded", len(regions) == 14, f"{len(regions)}")
    cats = c.get("/api/categories", params={"with_attributes": True}).json()
    check("13 categories with attributes seeded", len(cats) >= 13 and all("attributes" in x for x in cats), f"{len(cats)}")

    # registration + login + authorization
    email = f"smoke-{uuid.uuid4().hex[:8]}@example.uz"
    r = c.post("/api/auth/register", json={"email": email, "password": "Smoke12345", "full_name": "Smoke Test",
                                           "account_type": "buyer", "organization_name": "Smoke LLC"})
    ok = check("Register buyer", r.status_code == 201, f"HTTP {r.status_code} {r.text[:120]}")
    if ok:
        h = {"Authorization": f"Bearer {r.json()['access_token']}"}
        me = c.get("/api/auth/me", headers=h)
        check("Authenticated /auth/me", me.status_code == 200 and me.json()["role"] == "buyer", f"HTTP {me.status_code}")
        r = c.post("/api/admin/categories", headers=h, json={"slug": "smoke-x", "name_uz": "x", "name_ru": "x"})
        check("Buyer is forbidden from admin endpoints", r.status_code == 403, f"HTTP {r.status_code}")
    check("Anonymous is rejected on protected endpoints", c.get("/api/saved/products").status_code == 401)

    ov = c.get("/api/analytics/overview").json()
    check("Analytics overview", "active_offers" in ov, f"offers={ov.get('active_offers')} simulated={ov.get('simulated_active_offers')}")

    if ov.get("active_offers"):
        res = c.get("/api/products", params={"q": "cement", "has_offers": True}).json()
        check("Product search 'cement'", res["total"] >= 1, f"total={res['total']}")
        if res["items"]:
            pid = res["items"][0]["id"]
            cmp = c.get(f"/api/products/{pid}/compare", params={"quantity": 5000}).json()
            check("Offer comparison returns cheapest & best", cmp["cheapest_offer_id"] is not None and "weights" in cmp,
                  f"cheapest={cmp['cheapest_offer_id']} best={cmp['best_offer_id']} offers={len(cmp['offers'])}")
            hist = c.get(f"/api/products/{pid}/history", params={"granularity": "week"}).json()
            check("Price history", hist["status"] in ("ok", "insufficient_data"), f"status={hist['status']} points={len(hist['points'])}")
        demo = c.post("/api/auth/login", json={"email": "admin@demo.example.com", "password": "Demo12345!"})
        if check("Demo admin login (SEED_DEMO)", demo.status_code == 200, f"HTTP {demo.status_code} {demo.text[:160]}"):
            ha = {"Authorization": f"Bearer {demo.json()['access_token']}"}
            r = c.get("/api/market-data/sources", headers=ha)
            check("Admin: market data sources", r.status_code == 200 and len(r.json()) >= 3, f"{len(r.json()) if r.status_code == 200 else r.status_code}")
            r = c.get("/api/admin/audit-logs", headers=ha)
            check("Admin: audit log", r.status_code == 200, f"HTTP {r.status_code}")
            r = c.get("/api/admin/demo-data", headers=ha)
            check("Admin: simulated data is flagged", r.status_code == 200 and r.json().get("offers", 0) > 0, str(r.json() if r.status_code == 200 else r.status_code))
            for role in ("buyer", "supplier", "data"):
                rr = c.post("/api/auth/login", json={"email": f"{role}@demo.example.com", "password": "Demo12345!"})
                check(f"Demo {role} login", rr.status_code == 200, f"HTTP {rr.status_code}")
    else:
        print("[INFO] No offers in the database (SEED_DEMO=false?) — data-dependent checks skipped.")

    a_ = c.post("/api/assistant/ask", json={"question": "Where can I buy cement at the lowest price?"})
    check("AI assistant answers", a_.status_code == 200 and a_.json().get("answer"), f"mode={a_.json().get('mode') if a_.status_code == 200 else a_.status_code}")

    failed = [n for n, ok, _ in results if not ok]
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
