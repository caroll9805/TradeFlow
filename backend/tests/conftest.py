"""Test setup: isolated in-memory SQLite DB, reference seed, helper factories.
PostgreSQL is used in Docker; the ORM layer is dialect-neutral so tests run on SQLite."""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENVIRONMENT"] = "test"
os.environ["JWT_SECRET"] = "test-secret-key-which-is-long-enough-32b"
os.environ["LLM_PROVIDER"] = ""
os.environ["AUTH_RATE_LIMIT"] = "1000"

from datetime import timedelta  # noqa: E402
from decimal import Decimal  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

import app.models  # noqa: E402,F401
from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.ratelimit import limiter  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (  # noqa: E402
    Category,
    DataSource,
    Organization,
    OrganizationMember,
    Product,
    Region,
    Role,
    Supplier,
    Unit,
    UnitConversion,
    User,
)
from app.models.base import utcnow  # noqa: E402
from app.seed.base import seed_reference  # noqa: E402
from app.services.text import normalize_text  # noqa: E402


@pytest.fixture()
def db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    s = SessionLocal()
    seed_reference(s)
    limiter.reset()
    yield s
    s.close()


@pytest.fixture()
def client(db):
    return TestClient(app)


class Factory:
    def __init__(self, db, client):
        self.db, self.client = db, client

    def region(self, code: str) -> Region:
        return self.db.scalar(select(Region).where(Region.code == code))

    def unit(self, code: str) -> Unit:
        return self.db.scalar(select(Unit).where(Unit.code == code))

    def category(self, slug: str) -> Category:
        return self.db.scalar(select(Category).where(Category.slug == slug))

    def source(self, code: str) -> DataSource:
        return self.db.scalar(select(DataSource).where(DataSource.code == code))

    def user(self, role: str, email: str | None = None, org_name: str | None = None, password: str = "Passw0rd123"):
        r = self.db.scalar(select(Role).where(Role.code == role))
        email = email or f"{role}{self.db.scalar(select(User.id).order_by(User.id.desc())) or 0}x@test.uz"
        u = User(email=email, password_hash=hash_password(password), full_name=f"{role} user", role_id=r.id)
        org = Organization(name=org_name or f"{role} org {email}", org_type=role if role in ("buyer", "supplier", "manufacturer") else "platform")
        self.db.add_all([u, org])
        self.db.flush()
        self.db.add(OrganizationMember(organization_id=org.id, user_id=u.id))
        self.db.commit()
        self.db.refresh(u)
        return u, org

    def token(self, email: str, password: str = "Passw0rd123") -> dict:
        r = self.client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    def login_as(self, role: str):
        u, org = self.user(role)
        return u, org, self.token(u.email)

    def supplier(self, org: Organization | None, name: str, region_code: str, verification: str = "unverified",
                 rating: Decimal | None = None) -> Supplier:
        s = Supplier(organization_id=org.id if org else None, name=name, supplier_type="wholesaler",
                     region_id=self.region(region_code).id, verification_status=verification, rating_avg=rating)
        self.db.add(s)
        self.db.commit()
        return s

    def product(self, name: str, cat: str = "construction", base: str = "kg", terms: list | None = None,
                bag_kg: int | None = None, barcode: str | None = None) -> Product:
        p = Product(name=name, normalized_name=normalize_text(name), category_id=self.category(cat).id,
                    base_unit_id=self.unit(base).id, search_terms=terms or [], status="active", barcode=barcode)
        self.db.add(p)
        self.db.flush()
        if bag_kg:
            self.db.add(UnitConversion(product_id=p.id, from_unit_id=self.unit("bag").id, to_unit_id=self.unit(base).id,
                                       factor=Decimal(bag_kg)))
        self.db.commit()
        return p

    def offer(self, headers: dict, supplier: Supplier, product: Product, price, unit="kg", region=None, **kw):
        body = {"supplier_id": supplier.id, "product_id": product.id, "price": str(price), "unit_id": self.unit(unit).id,
                "region_id": (self.region(region) if region else supplier.region).id}
        body.update(kw)
        r = self.client.post("/api/offers", json=body, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()


@pytest.fixture()
def f(db, client):
    return Factory(db, client)


@pytest.fixture()
def admin(f):
    return f.login_as("super_admin")


__all__ = ["utcnow", "timedelta"]
