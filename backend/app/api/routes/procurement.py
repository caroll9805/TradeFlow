"""Saved items, quote requests (RFQ-lite), notifications. Organization-isolated."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import get_or_404, product_out, supplier_out
from app.core.database import get_db
from app.core.deps import can_manage_supplier, get_current_user, has, require
from app.models import (
    Notification,
    OrganizationMember,
    Product,
    QuoteRequest,
    QuoteResponse,
    SavedProduct,
    SavedSupplier,
    Supplier,
    Unit,
    User,
)
from app.models.base import utcnow
from app.schemas import QuoteRequestIn, QuoteResponseIn
from app.services.audit import audit

router = APIRouter(tags=["procurement"])


# ---------- saved
@router.get("/saved/products")
def saved_products(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedProduct).where(SavedProduct.user_id == user.id).order_by(SavedProduct.created_at.desc())).all()
    return [{"id": r.id, "created_at": r.created_at, "product": product_out(r.product)} for r in rows]


@router.put("/saved/products/{product_id}", status_code=204)
def save_product(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_or_404(db, Product, product_id, "Product")
    if not db.scalar(select(SavedProduct).where(SavedProduct.user_id == user.id, SavedProduct.product_id == product_id)):
        db.add(SavedProduct(user_id=user.id, product_id=product_id))
        db.commit()


@router.delete("/saved/products/{product_id}", status_code=204)
def unsave_product(product_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.scalar(select(SavedProduct).where(SavedProduct.user_id == user.id, SavedProduct.product_id == product_id))
    if r:
        db.delete(r)
        db.commit()


@router.get("/saved/suppliers")
def saved_suppliers(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SavedSupplier).where(SavedSupplier.user_id == user.id).order_by(SavedSupplier.created_at.desc())).all()
    return [{"id": r.id, "created_at": r.created_at, "supplier": supplier_out(r.supplier)} for r in rows]


@router.put("/saved/suppliers/{supplier_id}", status_code=204)
def save_supplier(supplier_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    get_or_404(db, Supplier, supplier_id, "Supplier")
    if not db.scalar(select(SavedSupplier).where(SavedSupplier.user_id == user.id, SavedSupplier.supplier_id == supplier_id)):
        db.add(SavedSupplier(user_id=user.id, supplier_id=supplier_id))
        db.commit()


@router.delete("/saved/suppliers/{supplier_id}", status_code=204)
def unsave_supplier(supplier_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = db.scalar(select(SavedSupplier).where(SavedSupplier.user_id == user.id, SavedSupplier.supplier_id == supplier_id))
    if r:
        db.delete(r)
        db.commit()


# ---------- quotes
def _quote_out(q: QuoteRequest) -> dict:
    return {"id": q.id, "status": q.status, "product": {"id": q.product.id, "name": q.product.name},
            "supplier": {"id": q.supplier.id, "name": q.supplier.name}, "quantity": q.quantity, "unit_id": q.unit_id,
            "delivery_region_id": q.delivery_region_id, "message": q.message, "created_at": q.created_at,
            "buyer_organization_id": q.buyer_organization_id,
            "responses": [{"id": r.id, "price": r.price, "currency": r.currency, "unit_id": r.unit_id,
                           "valid_until": r.valid_until, "message": r.message, "created_at": r.created_at}
                          for r in q.responses]}


def _notify_org(db: Session, org_id: int | None, kind: str, title: str, link: str) -> None:
    if not org_id:
        return
    for m in db.scalars(select(OrganizationMember).where(OrganizationMember.organization_id == org_id)).all():
        db.add(Notification(user_id=m.user_id, kind=kind, title=title, link=link))


@router.post("/quotes", status_code=201)
def create_quote(body: QuoteRequestIn, user: User = Depends(require("quotes.request")), db: Session = Depends(get_db)):
    if not user.organization_ids:
        raise HTTPException(403, "You must belong to an organization")
    sup = get_or_404(db, Supplier, body.supplier_id, "Supplier")
    prod = get_or_404(db, Product, body.product_id, "Product")
    get_or_404(db, Unit, body.unit_id, "Unit")
    q = QuoteRequest(buyer_organization_id=user.organization_ids[0], requested_by_id=user.id, **body.model_dump())
    db.add(q)
    db.flush()
    _notify_org(db, sup.organization_id, "quote_request", f"New quote request: {prod.name}", f"/supplier?quote={q.id}")
    audit(db, user, "create", "quote_request", q.id)
    db.commit()
    return _quote_out(q)


@router.get("/quotes/sent")
def sent_quotes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.organization_ids:
        return []
    rows = db.scalars(select(QuoteRequest).where(QuoteRequest.buyer_organization_id.in_(user.organization_ids))
                      .order_by(QuoteRequest.created_at.desc())).unique().all()
    return [_quote_out(q) for q in rows]


@router.get("/quotes/received")
def received_quotes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not user.organization_ids:
        return []
    rows = db.scalars(select(QuoteRequest).join(Supplier, Supplier.id == QuoteRequest.supplier_id)
                      .where(Supplier.organization_id.in_(user.organization_ids))
                      .order_by(QuoteRequest.created_at.desc())).unique().all()
    return [_quote_out(q) for q in rows]


@router.get("/quotes/{quote_id}")
def get_quote(quote_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = get_or_404(db, QuoteRequest, quote_id, "Quote request")
    if not (q.buyer_organization_id in user.organization_ids or can_manage_supplier(user, q.supplier)):
        raise HTTPException(404, "Quote request not found")  # don't leak existence across organizations
    return _quote_out(q)


@router.post("/quotes/{quote_id}/responses", status_code=201)
def respond_quote(quote_id: int, body: QuoteResponseIn, user: User = Depends(require("quotes.respond")),
                  db: Session = Depends(get_db)):
    q = get_or_404(db, QuoteRequest, quote_id, "Quote request")
    if not can_manage_supplier(user, q.supplier):
        raise HTTPException(404, "Quote request not found")
    if q.status in ("closed", "cancelled"):
        raise HTTPException(409, "Quote request is closed")
    r = QuoteResponse(quote_request_id=q.id, responded_by_id=user.id, **body.model_dump())
    db.add(r)
    q.status = "answered"
    _notify_org(db, q.buyer_organization_id, "quote_response", f"Quote received: {q.product.name}", f"/procurement?quote={q.id}")
    db.commit()
    db.refresh(q)
    return _quote_out(q)


@router.post("/quotes/{quote_id}/close")
def close_quote(quote_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = get_or_404(db, QuoteRequest, quote_id, "Quote request")
    if q.buyer_organization_id not in user.organization_ids:
        raise HTTPException(404, "Quote request not found")
    q.status = "closed"
    db.commit()
    return _quote_out(q)


# ---------- notifications
@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id)
                      .order_by(Notification.created_at.desc()).limit(50)).all()
    return [{"id": n.id, "kind": n.kind, "title": n.title, "body": n.body, "link": n.link, "read_at": n.read_at,
             "created_at": n.created_at} for n in rows]


@router.post("/notifications/{nid}/read", status_code=204)
def read_notification(nid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Not found")
    n.read_at = utcnow()
    db.commit()


__all__ = ["has"]
