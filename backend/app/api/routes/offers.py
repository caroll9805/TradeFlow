from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import PageParams, get_or_404, offer_out, paginate
from app.core.database import get_db
from app.core.deps import ensure_can_manage_supplier, get_current_user, has
from app.models import DataSource, Offer, Product, Region, Supplier, SupplierLocation, Unit, User
from app.schemas import OfferIn, OfferUpdate
from app.services.audit import audit
from app.services.currency import MissingExchangeRate
from app.services.pricing import apply_offer_price
from app.services.units import try_conversion_factor

router = APIRouter(prefix="/offers", tags=["offers"])


def _submission_source(db: Session) -> DataSource:
    ds = db.scalar(select(DataSource).where(DataSource.code == "supplier_submissions"))
    if ds is None:
        raise HTTPException(500, "Data source 'supplier_submissions' is not configured; run the seed")
    return ds


@router.get("")
def list_offers(product_id: int | None = None, supplier_id: int | None = None, region_id: int | None = None,
                category_id: int | None = None, price_type: str | None = None, active: bool = True,
                include_simulated: bool = True, sort: Literal["updated", "price"] = "updated",
                p: PageParams = Depends(), db: Session = Depends(get_db)):
    stmt = select(Offer).where(Offer.is_active.is_(active))
    if product_id:
        stmt = stmt.where(Offer.product_id == product_id)
    if supplier_id:
        stmt = stmt.where(Offer.supplier_id == supplier_id)
    if region_id:
        stmt = stmt.where(Offer.region_id == region_id)
    if category_id:
        stmt = stmt.join(Product, Product.id == Offer.product_id).where(Product.category_id == category_id)
    if price_type:
        stmt = stmt.where(Offer.price_type == price_type)
    if not include_simulated:
        stmt = stmt.where(Offer.is_simulated.is_(False))
    stmt = stmt.order_by(Offer.price_updated_at.desc() if sort == "updated" else Offer.price_per_base_unit_uzs.asc(), Offer.id)
    return paginate(db, stmt, p, offer_out)


@router.get("/mine")
def my_offers(include_inactive: bool = True, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.organization_ids:
        return []
    stmt = select(Offer).join(Supplier, Supplier.id == Offer.supplier_id).where(Supplier.organization_id.in_(user.organization_ids))
    if not include_inactive:
        stmt = stmt.where(Offer.is_active.is_(True))
    return [offer_out(o) for o in db.scalars(stmt.order_by(Offer.updated_at.desc())).unique().all()]


@router.post("", status_code=201)
def create_offer(body: OfferIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    supplier = get_or_404(db, Supplier, body.supplier_id, "Supplier")
    ensure_can_manage_supplier(user, supplier)
    product = get_or_404(db, Product, body.product_id, "Product")
    if product.status != "active":
        raise HTTPException(422, "Product is not active")
    unit = get_or_404(db, Unit, body.unit_id, "Unit")
    if not db.get(Region, body.region_id):
        raise HTTPException(422, "Unknown region")
    if body.location_id:
        loc = db.get(SupplierLocation, body.location_id)
        if not loc or loc.supplier_id != supplier.id:
            raise HTTPException(422, "Location does not belong to this supplier")
    if try_conversion_factor(db, unit, product.base_unit, product.id) is None:
        raise HTTPException(422, f"Unit '{unit.code}' cannot be converted to the product's base unit "
                                 f"'{product.base_unit.code}'. Add a product unit conversion first.")
    if body.valid_from and body.valid_until and body.valid_until <= body.valid_from:
        raise HTTPException(422, "valid_until must be after valid_from")
    ds = _submission_source(db)
    o = Offer(supplier_id=supplier.id, product_id=product.id, original_price=body.price, original_currency=body.currency,
              unit_id=unit.id, price_uzs=body.price, moq=body.moq, available_qty=body.available_qty,
              region_id=body.region_id, district_id=body.district_id, location_id=body.location_id,
              delivery_available=body.delivery_available, delivery_cost_uzs=body.delivery_cost_uzs,
              delivery_regions=body.delivery_regions, other_fees_uzs=body.other_fees_uzs,
              valid_from=body.valid_from, valid_until=body.valid_until, price_type=body.price_type,
              verification_status="unverified", provenance_kind="supplier_declared", data_source_id=ds.id,
              source_url=str(body.source_url) if body.source_url else None, original_product_name=product.name,
              is_simulated=False)
    o.product, o.data_source = product, ds
    db.add(o)
    db.flush()
    try:
        apply_offer_price(db, o, price=body.price, currency=body.currency, unit=unit, collection_method="supplier_form")
    except MissingExchangeRate as e:
        db.rollback()
        raise HTTPException(422, str(e))
    if product.category not in supplier.categories:
        supplier.categories.append(product.category)
    audit(db, user, "create", "offer", o.id, {"price": body.price, "currency": body.currency, "product_id": product.id})
    db.commit()
    db.refresh(o)
    return offer_out(o)


@router.patch("/{offer_id}")
def update_offer(offer_id: int, body: OfferUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = get_or_404(db, Offer, offer_id, "Offer")
    if not has(user, "offers.manage_all"):
        ensure_can_manage_supplier(user, o.supplier)
    data = body.model_dump(exclude_unset=True)
    before = {"price": o.original_price, "currency": o.original_currency, "unit_id": o.unit_id}
    price_fields = {"price", "currency", "unit_id"} & data.keys()
    for k in ("moq", "available_qty", "delivery_available", "delivery_cost_uzs", "delivery_regions", "other_fees_uzs",
              "valid_until", "is_active"):
        if k in data:
            setattr(o, k, data[k])
    if price_fields:
        unit = get_or_404(db, Unit, data.get("unit_id", o.unit_id), "Unit")
        if try_conversion_factor(db, unit, o.product.base_unit, o.product_id) is None:
            raise HTTPException(422, "Unit not convertible to the product's base unit")
        try:
            # Writes a NEW observation — history is never overwritten.
            apply_offer_price(db, o, price=data.get("price", o.original_price), currency=data.get("currency", o.original_currency),
                              unit=unit, collection_method="supplier_form")
        except MissingExchangeRate as e:
            db.rollback()
            raise HTTPException(422, str(e))
    audit(db, user, "update", "offer", o.id, {"before": before, "changes": data})
    db.commit()
    db.refresh(o)
    return offer_out(o)


@router.delete("/{offer_id}", status_code=204)
def deactivate_offer(offer_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    o = get_or_404(db, Offer, offer_id, "Offer")
    if not has(user, "offers.manage_all"):
        ensure_can_manage_supplier(user, o.supplier)
    o.is_active = False
    audit(db, user, "deactivate", "offer", o.id)
    db.commit()


@router.post("/{offer_id}/verification")
def verify_offer(offer_id: int, status: Literal["verified", "rejected", "unverified"],
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not has(user, "market_data.manage"):
        raise HTTPException(403, "Insufficient permissions")
    o = get_or_404(db, Offer, offer_id, "Offer")
    o.verification_status = status
    audit(db, user, "verification", "offer", o.id, {"status": status})
    db.commit()
    return offer_out(o)
