"""Public reference data: regions, units, categories (+ dynamic attributes), exchange rates."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import category_out, get_or_404, region_out, unit_out
from app.core.database import get_db
from app.models import Category, District, ExchangeRate, Region, Unit, UnitConversion
from app.services.market_data.base import registry

router = APIRouter(tags=["reference"])


@router.get("/regions")
def regions(db: Session = Depends(get_db)):
    return [region_out(r) for r in db.scalars(select(Region).order_by(Region.sort_order, Region.id)).all()]


@router.get("/regions/{region_id}/districts")
def districts(region_id: int, db: Session = Depends(get_db)):
    get_or_404(db, Region, region_id)
    return [{"id": d.id, "region_id": d.region_id, "name_uz": d.name_uz, "name_ru": d.name_ru}
            for d in db.scalars(select(District).where(District.region_id == region_id).order_by(District.name_uz)).all()]


@router.get("/units")
def units(db: Session = Depends(get_db)):
    return [unit_out(u) for u in db.scalars(select(Unit).order_by(Unit.dimension, Unit.id)).all()]


@router.get("/unit-conversions")
def unit_conversions(product_id: int | None = None, db: Session = Depends(get_db)):
    q = select(UnitConversion)
    if product_id:
        q = q.where(UnitConversion.product_id == product_id)
    return [{"id": c.id, "product_id": c.product_id, "from_unit_id": c.from_unit_id, "to_unit_id": c.to_unit_id,
             "factor": c.factor} for c in db.scalars(q).all()]


@router.get("/categories")
def categories(include_inactive: bool = False, with_attributes: bool = False, db: Session = Depends(get_db)):
    q = select(Category).order_by(Category.sort_order, Category.id)
    if not include_inactive:
        q = q.where(Category.is_active.is_(True))
    return [category_out(c, with_attributes) for c in db.scalars(q).unique().all()]


@router.get("/categories/{category_id}")
def category(category_id: int, db: Session = Depends(get_db)):
    return category_out(get_or_404(db, Category, category_id), with_attributes=True)


@router.get("/exchange-rates")
def exchange_rates(db: Session = Depends(get_db)):
    rows = db.scalars(select(ExchangeRate).order_by(ExchangeRate.currency, ExchangeRate.as_of.desc())).all()
    return [{"id": r.id, "currency": r.currency, "rate_to_uzs": r.rate_to_uzs, "as_of": r.as_of, "source": r.source}
            for r in rows]


@router.get("/connector-types")
def connector_types():
    return [{"type": k, "description": c.description, "config_schema": c.config_schema,
             "requires_terms_permission": c.requires_terms_permission} for k, c in registry().items()]
