import json
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, and_, exists, func, or_, select
from sqlalchemy.orm import Session

from app.api.common import PageParams, get_or_404, observation_out, paginate, product_out
from app.core.database import get_db
from app.core.deps import get_optional_user, has, require
from app.models import (
    Category,
    Manufacturer,
    Offer,
    PriceObservation,
    Product,
    ProductAttributeValue,
    ProductImage,
    SearchEvent,
    Unit,
    User,
)
from app.schemas import ManufacturerIn, ProductIn
from app.services import analytics
from app.services.audit import audit
from app.services.catalog import validate_and_apply_attributes
from app.services.comparison import CompareParams, compare_offers, regional_prices
from app.services.text import normalize_text

router = APIRouter(tags=["products"])


def _offer_stats_subq(region_id: int | None, include_simulated: bool, price_type: str | None):
    conds = [Offer.is_active.is_(True), Offer.price_per_base_unit_uzs.is_not(None)]
    if region_id:
        conds.append(Offer.region_id == region_id)
    if not include_simulated:
        conds.append(Offer.is_simulated.is_(False))
    if price_type:
        conds.append(Offer.price_type == price_type)
    return (select(Offer.product_id.label("pid"), func.count(Offer.id).label("n"),
                   func.min(Offer.price_per_base_unit_uzs).label("pmin"), func.max(Offer.price_per_base_unit_uzs).label("pmax"),
                   func.avg(Offer.price_per_base_unit_uzs).label("pavg"), func.count(func.distinct(Offer.region_id)).label("nreg"),
                   func.max(Offer.price_updated_at).label("last"))
            .where(*conds).group_by(Offer.product_id).subquery())


@router.get("/products")
def list_products(
    q: str | None = None, category_id: int | None = None, brand: str | None = None,
    region_id: int | None = None, manufacturer_id: int | None = None,
    origin_type: Literal["domestic", "import", "unknown"] | None = None,
    price_type: Literal["wholesale", "retail", "negotiated", "other"] | None = None,
    price_min: Decimal | None = Query(None, ge=0), price_max: Decimal | None = Query(None, ge=0),
    has_offers: bool = False, include_simulated: bool = True, status: str = "active",
    attrs: str | None = Query(None, description='JSON object {"<attribute_id>": value}'),
    sort: Literal["name", "price_asc", "price_desc", "offers", "updated"] = "name",
    p: PageParams = Depends(), db: Session = Depends(get_db), user: User | None = Depends(get_optional_user),
):
    st = _offer_stats_subq(region_id, include_simulated, price_type)
    stmt = select(Product).outerjoin(st, st.c.pid == Product.id)
    if not has(user, "catalog.manage"):
        stmt = stmt.where(Product.status == "active")
    elif status != "any":
        stmt = stmt.where(Product.status == status)
    if not include_simulated:
        stmt = stmt.where(Product.is_simulated.is_(False))
    if q:
        nq = normalize_text(q)
        like = [Product.normalized_name.contains(t) for t in nq.split()[:6]] if nq else []
        stmt = stmt.where(or_(and_(*like) if like else False, Product.barcode == q.strip(), Product.sku == q.strip(),
                              func.lower(Product.brand) == q.strip().lower()))
    if category_id:
        sub_ids = [category_id] + list(db.scalars(select(Category.id).where(Category.parent_id == category_id)))
        stmt = stmt.where(Product.category_id.in_(sub_ids))
    if brand:
        stmt = stmt.where(func.lower(Product.brand) == brand.lower())
    if manufacturer_id:
        stmt = stmt.where(Product.manufacturer_id == manufacturer_id)
    if origin_type:
        stmt = stmt.where(Product.origin_type == origin_type)
    if has_offers or region_id or price_type:
        stmt = stmt.where(st.c.n > 0)
    if price_min is not None:
        stmt = stmt.where(st.c.pmin >= price_min)
    if price_max is not None:
        stmt = stmt.where(st.c.pmin <= price_max)
    if attrs:
        try:
            af = json.loads(attrs)
            assert isinstance(af, dict)
        except Exception:
            raise HTTPException(422, "attrs must be a JSON object")
        for aid, val in af.items():
            if val in (None, ""):
                continue
            cond = [ProductAttributeValue.product_id == Product.id, ProductAttributeValue.attribute_id == int(aid)]
            if isinstance(val, bool):
                cond.append(ProductAttributeValue.value_bool.is_(val))
            elif isinstance(val, (int, float)):
                cond.append(ProductAttributeValue.value_number == Decimal(str(val)))
            else:
                cond.append(or_(func.lower(ProductAttributeValue.value_text) == str(val).lower(),
                                ProductAttributeValue.value_json.cast(String).contains(f'"{val}"')))
            stmt = stmt.where(exists().where(*cond))
    order = {"name": [Product.name], "price_asc": [st.c.pmin.is_(None), st.c.pmin], "price_desc": [st.c.pmin.is_(None), st.c.pmin.desc()],
             "offers": [st.c.n.is_(None), st.c.n.desc()], "updated": [st.c.last.is_(None), st.c.last.desc()]}[sort]
    stmt = stmt.order_by(*order, Product.id)

    if q and p.page == 1:
        db.add(SearchEvent(query=q[:300], category_id=category_id, region_id=region_id, user_id=user.id if user else None))
        db.commit()

    page = paginate(db, stmt, p, lambda x: x)
    ids = [x.id for x in page["items"]]
    stats = {r.pid: r for r in db.execute(select(st).where(st.c.pid.in_(ids))).all()} if ids else {}

    def m(prod: Product) -> dict:
        s = stats.get(prod.id)
        return product_out(prod, {"offer_stats": {"offers": s.n if s else 0, "min_per_base_unit_uzs": s.pmin if s else None,
                                                  "max_per_base_unit_uzs": s.pmax if s else None,
                                                  "avg_per_base_unit_uzs": round(Decimal(s.pavg), 2) if s and s.pavg is not None else None,
                                                  "regions": s.nreg if s else 0, "last_updated": s.last if s else None}})
    page["items"] = [m(x) for x in page["items"]]
    return page


@router.get("/products/brands")
def brands(category_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Product.brand).where(Product.brand.is_not(None), Product.status == "active").distinct().order_by(Product.brand)
    if category_id:
        q = q.where(Product.category_id == category_id)
    return [b for b in db.scalars(q).all()]


@router.get("/products/{product_id}")
def get_product(product_id: int, db: Session = Depends(get_db), user: User | None = Depends(get_optional_user)):
    prod = get_or_404(db, Product, product_id, "Product")
    if prod.status != "active" and not has(user, "catalog.manage"):
        raise HTTPException(404, "Product not found")
    db.add(SearchEvent(query=f"view:{product_id}", product_id=product_id, category_id=prod.category_id,
                       user_id=user.id if user else None))
    db.commit()
    return product_out(prod)


def _check_refs(db: Session, body: ProductIn) -> None:
    if not db.get(Category, body.category_id):
        raise HTTPException(422, "Unknown category")
    if not db.get(Unit, body.base_unit_id):
        raise HTTPException(422, "Unknown unit")
    if body.manufacturer_id and not db.get(Manufacturer, body.manufacturer_id):
        raise HTTPException(422, "Unknown manufacturer")


@router.post("/products", status_code=201)
def create_product(body: ProductIn, db: Session = Depends(get_db), user: User = Depends(require("products.create"))):
    _check_refs(db, body)
    if body.barcode and db.scalar(select(Product).where(Product.barcode == body.barcode)):
        raise HTTPException(409, "A product with this barcode already exists")
    data = body.model_dump(exclude={"attributes", "image_urls"})
    if not has(user, "catalog.manage"):
        data["status"] = "active" if body.status in ("active", "draft") else "draft"
    prod = Product(**data, normalized_name=normalize_text(body.name))
    db.add(prod)
    db.flush()
    validate_and_apply_attributes(db, prod, [a.model_dump() for a in body.attributes])
    for i, u in enumerate(body.image_urls):
        prod.images.append(ProductImage(url=str(u), sort_order=i))
    audit(db, user, "create", "product", prod.id, {"name": prod.name})
    db.commit()
    return product_out(prod)


@router.put("/products/{product_id}")
def update_product(product_id: int, body: ProductIn, db: Session = Depends(get_db),
                   user: User = Depends(require("catalog.manage"))):
    prod = get_or_404(db, Product, product_id, "Product")
    _check_refs(db, body)
    before = product_out(prod)
    for k, v in body.model_dump(exclude={"attributes", "image_urls"}).items():
        setattr(prod, k, v)
    prod.normalized_name = normalize_text(body.name)
    validate_and_apply_attributes(db, prod, [a.model_dump() for a in body.attributes])
    prod.images.clear()
    for i, u in enumerate(body.image_urls):
        prod.images.append(ProductImage(url=str(u), sort_order=i))
    audit(db, user, "update", "product", prod.id, {"before": {"name": before["name"], "status": before["status"]},
                                                   "after": {"name": prod.name, "status": prod.status}})
    db.commit()
    return product_out(prod)


@router.delete("/products/{product_id}", status_code=204)
def archive_product(product_id: int, db: Session = Depends(get_db), user: User = Depends(require("catalog.manage"))):
    prod = get_or_404(db, Product, product_id, "Product")
    prod.status = "archived"  # soft delete keeps price history intact
    audit(db, user, "archive", "product", prod.id)
    db.commit()


@router.get("/products/{product_id}/compare")
def compare(product_id: int, quantity: Decimal | None = Query(None, gt=0), region_id: int | None = None,
            buyer_region_id: int | None = None, price_type: str | None = None, verified_only: bool = False,
            include_simulated: bool = True, db: Session = Depends(get_db)):
    get_or_404(db, Product, product_id, "Product")
    return compare_offers(db, CompareParams(product_id=product_id, quantity=quantity, region_id=region_id,
                                            buyer_region_id=buyer_region_id, price_type=price_type,
                                            verified_only=verified_only, include_simulated=include_simulated))


@router.get("/products/{product_id}/regional")
def regional(product_id: int, include_simulated: bool = True, db: Session = Depends(get_db)):
    get_or_404(db, Product, product_id, "Product")
    return regional_prices(db, product_id, include_simulated)


@router.get("/products/{product_id}/history")
def history(product_id: int, granularity: Literal["day", "week", "month"] = "week", region_id: int | None = None,
            days: int = Query(180, ge=7, le=1095), include_simulated: bool = True, price_type: str | None = None,
            db: Session = Depends(get_db)):
    get_or_404(db, Product, product_id, "Product")
    return analytics.price_history(db, product_id, granularity=granularity, region_id=region_id, days=days,
                                   include_simulated=include_simulated, price_type=price_type)


@router.get("/products/{product_id}/forecast")
def forecast(product_id: int, region_id: int | None = None, db: Session = Depends(get_db)):
    get_or_404(db, Product, product_id, "Product")
    return analytics.forecast(db, product_id, region_id=region_id)


@router.get("/products/{product_id}/supply-demand")
def supply_demand(product_id: int, days: int = Query(30, ge=1, le=365), db: Session = Depends(get_db)):
    get_or_404(db, Product, product_id, "Product")
    return analytics.supply_demand(db, product_id, days)


@router.get("/products/{product_id}/observations")
def observations(product_id: int, region_id: int | None = None, include_simulated: bool = True,
                 p: PageParams = Depends(), db: Session = Depends(get_db)):
    get_or_404(db, Product, product_id, "Product")
    stmt = select(PriceObservation).where(PriceObservation.product_id == product_id)
    if region_id:
        stmt = stmt.where(PriceObservation.region_id == region_id)
    if not include_simulated:
        stmt = stmt.where(PriceObservation.is_simulated.is_(False))
    return paginate(db, stmt.order_by(PriceObservation.observed_at.desc()), p, observation_out)


@router.get("/manufacturers")
def manufacturers(q: str | None = None, db: Session = Depends(get_db)):
    stmt = select(Manufacturer).order_by(Manufacturer.name)
    if q:
        stmt = stmt.where(func.lower(Manufacturer.name).contains(q.lower()))
    return [{"id": m.id, "name": m.name, "country_code": m.country_code, "website": m.website,
             "is_simulated": m.is_simulated} for m in db.scalars(stmt.limit(200)).all()]


@router.post("/manufacturers", status_code=201)
def create_manufacturer(body: ManufacturerIn, db: Session = Depends(get_db), user: User = Depends(require("products.create"))):
    m = Manufacturer(name=body.name, country_code=body.country_code, website=str(body.website) if body.website else None)
    db.add(m)
    db.flush()
    audit(db, user, "create", "manufacturer", m.id, {"name": m.name})
    db.commit()
    return {"id": m.id, "name": m.name, "country_code": m.country_code, "website": m.website}
