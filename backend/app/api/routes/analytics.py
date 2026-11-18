from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import offer_out
from app.core.database import get_db
from app.core.deps import require
from app.models import Offer, Product
from app.services import analytics

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview")
def overview(include_simulated: bool = True, category_id: int | None = None, region_id: int | None = None,
             db: Session = Depends(get_db)):
    return analytics.overview(db, include_simulated, category_id, region_id)


@router.get("/movers")
def movers(category_id: int | None = None, region_id: int | None = None, include_simulated: bool = True,
           limit: int = Query(10, ge=1, le=50), db: Session = Depends(get_db)):
    return analytics.price_movers(db, category_id=category_id, region_id=region_id,
                                  include_simulated=include_simulated, limit=limit)


@router.get("/regions")
def regions(category_id: int | None = None, include_simulated: bool = True, db: Session = Depends(get_db)):
    return analytics.regional_overview(db, category_id=category_id, include_simulated=include_simulated)


@router.get("/freshness")
def freshness(db: Session = Depends(get_db)):
    return analytics.source_freshness(db)


@router.get("/recent-offers")
def recent(limit: int = Query(10, ge=1, le=50), include_simulated: bool = True, category_id: int | None = None,
           region_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Offer).where(Offer.is_active.is_(True))
    if not include_simulated:
        q = q.where(Offer.is_simulated.is_(False))
    if category_id:
        q = q.join(Product, Product.id == Offer.product_id).where(Product.category_id == category_id)
    if region_id:
        q = q.where(Offer.region_id == region_id)
    return [offer_out(o) for o in db.scalars(q.order_by(Offer.price_updated_at.desc()).limit(limit)).unique().all()]


@router.get("/anomalies", dependencies=[Depends(require("market_data.manage"))])
def anomalies(product_id: int | None = None, category_id: int | None = None, days: int = Query(90, ge=7, le=730),
              include_simulated: bool = True, db: Session = Depends(get_db)):
    return analytics.detect_anomalies(db, product_id=product_id, category_id=category_id, days=days,
                                      include_simulated=include_simulated)
