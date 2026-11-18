from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.common import PageParams, get_or_404, offer_out, paginate, supplier_out
from app.core.database import get_db
from app.core.deps import ensure_can_manage_supplier, get_current_user, has, require
from app.models import Category, Offer, Region, Supplier, SupplierLocation, SupplierRating, User, VerificationRequest
from app.models.base import utcnow
from app.schemas import RatingIn, SupplierIn, VerificationDecision
from app.services.audit import audit

router = APIRouter(prefix="/suppliers", tags=["suppliers"])


@router.get("")
def list_suppliers(q: str | None = None, region_id: int | None = None, category_id: int | None = None,
                   supplier_type: str | None = None, verified_only: bool = False, include_simulated: bool = True,
                   product_id: int | None = None,
                   sort: Literal["name", "rating", "offers"] = "name",
                   p: PageParams = Depends(), db: Session = Depends(get_db)):
    offers_n = (select(Offer.supplier_id.label("sid"), func.count(Offer.id).label("n"))
                .where(Offer.is_active.is_(True)).group_by(Offer.supplier_id).subquery())
    stmt = select(Supplier).outerjoin(offers_n, offers_n.c.sid == Supplier.id).where(Supplier.is_active.is_(True))
    if q:
        stmt = stmt.where(func.lower(Supplier.name).contains(q.lower().strip()))
    if region_id:
        stmt = stmt.where(Supplier.region_id == region_id)
    if category_id:
        stmt = stmt.where(Supplier.categories.any(Category.id == category_id))
    if supplier_type:
        stmt = stmt.where(Supplier.supplier_type == supplier_type)
    if verified_only:
        stmt = stmt.where(Supplier.verification_status == "verified")
    if not include_simulated:
        stmt = stmt.where(Supplier.is_simulated.is_(False))
    if product_id:
        stmt = stmt.where(Supplier.id.in_(select(Offer.supplier_id).where(Offer.product_id == product_id, Offer.is_active.is_(True))))
    order = {"name": [Supplier.name], "rating": [Supplier.rating_avg.is_(None), Supplier.rating_avg.desc()],
             "offers": [offers_n.c.n.is_(None), offers_n.c.n.desc()]}[sort]
    page = paginate(db, stmt.order_by(*order, Supplier.id), p, lambda s: s)
    ids = [s.id for s in page["items"]]
    counts = dict(db.execute(select(offers_n.c.sid, offers_n.c.n).where(offers_n.c.sid.in_(ids))).all()) if ids else {}
    page["items"] = [{**supplier_out(s), "active_offers": counts.get(s.id, 0)} for s in page["items"]]
    return page


@router.get("/mine")
def my_suppliers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.organization_ids:
        return []
    rows = db.scalars(select(Supplier).where(Supplier.organization_id.in_(user.organization_ids))).unique().all()
    return [supplier_out(s, detail=True) for s in rows]


@router.get("/{supplier_id}")
def get_supplier(supplier_id: int, db: Session = Depends(get_db)):
    s = get_or_404(db, Supplier, supplier_id, "Supplier")
    offers = db.scalars(select(Offer).where(Offer.supplier_id == s.id, Offer.is_active.is_(True))
                        .order_by(Offer.price_updated_at.desc()).limit(200)).unique().all()
    return {**supplier_out(s, detail=True), "offers": [offer_out(o) for o in offers]}


def _apply(db: Session, s: Supplier, body: SupplierIn) -> None:
    if not db.get(Region, body.region_id):
        raise HTTPException(422, "Unknown region")
    data = body.model_dump(exclude={"category_ids", "locations"})
    data["website"] = str(body.website) if body.website else None
    data["social_links"] = {k: str(v) for k, v in body.social_links.items()}
    for k, v in data.items():
        setattr(s, k, v)
    cats = db.scalars(select(Category).where(Category.id.in_(body.category_ids))).all() if body.category_ids else []
    if len(cats) != len(set(body.category_ids)):
        raise HTTPException(422, "Unknown category")
    s.categories = list(cats)
    s.locations.clear()
    for loc in body.locations:
        s.locations.append(SupplierLocation(**loc.model_dump()))


@router.post("", status_code=201)
def create_supplier(body: SupplierIn, user: User = Depends(require("suppliers.manage_own")), db: Session = Depends(get_db)):
    if not has(user, "suppliers.manage_all") and not user.organization_ids:
        raise HTTPException(403, "You must belong to an organization")
    s = Supplier(organization_id=None if has(user, "suppliers.manage_all") else user.organization_ids[0],
                 verification_status="unverified", name=body.name, supplier_type=body.supplier_type, region_id=body.region_id)
    db.add(s)
    _apply(db, s, body)
    db.flush()
    audit(db, user, "create", "supplier", s.id, {"name": s.name})
    db.commit()
    return supplier_out(s, detail=True)


@router.put("/{supplier_id}")
def update_supplier(supplier_id: int, body: SupplierIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = get_or_404(db, Supplier, supplier_id, "Supplier")
    ensure_can_manage_supplier(user, s)
    _apply(db, s, body)
    audit(db, user, "update", "supplier", s.id, {"name": s.name})
    db.commit()
    return supplier_out(s, detail=True)


@router.post("/{supplier_id}/verification-request", status_code=201)
def request_verification(supplier_id: int, evidence: str | None = None, user: User = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    s = get_or_404(db, Supplier, supplier_id, "Supplier")
    ensure_can_manage_supplier(user, s)
    if s.verification_status == "verified":
        raise HTTPException(409, "Already verified")
    open_ = db.scalar(select(VerificationRequest).where(VerificationRequest.target_type == "supplier",
                                                        VerificationRequest.target_id == s.id,
                                                        VerificationRequest.status == "pending"))
    if open_:
        raise HTTPException(409, "A verification request is already pending")
    vr = VerificationRequest(target_type="supplier", target_id=s.id, requested_by_id=user.id, evidence=(evidence or "")[:5000])
    s.verification_status = "pending"
    db.add(vr)
    audit(db, user, "request_verification", "supplier", s.id)
    db.commit()
    return {"id": vr.id, "status": vr.status}


@router.post("/{supplier_id}/verification")
def set_verification(supplier_id: int, body: VerificationDecision, user: User = Depends(require("suppliers.verify")),
                     db: Session = Depends(get_db)):
    s = get_or_404(db, Supplier, supplier_id, "Supplier")
    before = s.verification_status
    s.verification_status = body.status
    s.verified_at = utcnow() if body.status == "verified" else None
    s.verified_by_id = user.id if body.status == "verified" else None
    for vr in db.scalars(select(VerificationRequest).where(VerificationRequest.target_type == "supplier",
                                                           VerificationRequest.target_id == s.id,
                                                           VerificationRequest.status == "pending")).all():
        vr.status = "approved" if body.status == "verified" else "rejected"
        vr.reviewer_notes, vr.reviewed_by_id, vr.reviewed_at = body.notes, user.id, utcnow()
    audit(db, user, "verification", "supplier", s.id, {"from": before, "to": body.status, "notes": body.notes})
    db.commit()
    return supplier_out(s, detail=True)


@router.post("/{supplier_id}/ratings", status_code=201)
def rate(supplier_id: int, body: RatingIn, user: User = Depends(require("quotes.request")), db: Session = Depends(get_db)):
    s = get_or_404(db, Supplier, supplier_id, "Supplier")
    if not user.organization_ids:
        raise HTTPException(403, "You must belong to an organization")
    if s.organization_id in user.organization_ids:
        raise HTTPException(403, "You cannot rate your own supplier profile")
    org_id = user.organization_ids[0]
    r = db.scalar(select(SupplierRating).where(SupplierRating.supplier_id == s.id, SupplierRating.organization_id == org_id))
    if r is None:
        r = SupplierRating(supplier_id=s.id, organization_id=org_id, user_id=user.id, score=body.score)
        db.add(r)
    r.score, r.comment = body.score, body.comment
    db.flush()
    avg, n = db.execute(select(func.avg(SupplierRating.score), func.count(SupplierRating.id))
                        .where(SupplierRating.supplier_id == s.id)).one()
    s.rating_avg, s.rating_count = round(avg, 2), n
    db.commit()
    return {"rating_avg": s.rating_avg, "rating_count": s.rating_count}
