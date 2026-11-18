"""Platform administration. Every configurable business rule is editable here — no code changes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.api.common import PageParams, attribute_out, category_out, get_or_404, paginate, region_out, unit_out, user_out
from app.core.database import get_db
from app.core.deps import require
from app.models import (
    AttributeOption,
    AuditLog,
    Category,
    CategoryAttribute,
    DataSource,
    District,
    ExchangeRate,
    Manufacturer,
    Offer,
    Organization,
    Permission,
    PlatformSetting,
    PriceObservation,
    Product,
    QuoteRequest,
    Region,
    Role,
    SearchEvent,
    SubscriptionPlan,
    Supplier,
    Unit,
    UnitConversion,
    User,
)
from app.schemas import (
    CategoryAttributeIn,
    CategoryIn,
    DistrictIn,
    ExchangeRateIn,
    RegionIn,
    RolePermissionsIn,
    SettingIn,
    UnitConversionIn,
    UnitIn,
    UserAdminUpdate,
)
from app.services.audit import audit

router = APIRouter(prefix="/admin", tags=["admin"])
CAT = Depends(require("catalog.manage"))


# ---------- users & roles
@router.get("/users", dependencies=[Depends(require("users.manage"))])
def users(q: str | None = None, role: str | None = None, p: PageParams = Depends(), db: Session = Depends(get_db)):
    stmt = select(User)
    if q:
        stmt = stmt.where(func.lower(User.email).contains(q.lower()) | func.lower(User.full_name).contains(q.lower()))
    if role:
        stmt = stmt.join(Role).where(Role.code == role)
    return paginate(db, stmt.order_by(User.id), p, user_out)


@router.patch("/users/{uid}")
def update_user(uid: int, body: UserAdminUpdate, admin: User = Depends(require("users.manage")), db: Session = Depends(get_db)):
    u = get_or_404(db, User, uid, "User")
    if u.id == admin.id and body.is_active is False:
        raise HTTPException(422, "You cannot deactivate yourself")
    changes = {}
    if body.role_code:
        role = db.scalar(select(Role).where(Role.code == body.role_code))
        if not role:
            raise HTTPException(422, "Unknown role")
        if role.code == "super_admin" and "roles.manage" not in admin.permission_codes:
            raise HTTPException(403, "Insufficient permissions")
        changes["role"] = [u.role.code, role.code]
        u.role_id, u.role = role.id, role
        u.token_version += 1
    if body.is_active is not None:
        changes["is_active"] = [u.is_active, body.is_active]
        u.is_active = body.is_active
        if not body.is_active:
            u.token_version += 1
    audit(db, admin, "update", "user", u.id, changes)
    db.commit()
    return user_out(u)


@router.get("/roles", dependencies=[Depends(require("users.manage"))])
def roles(db: Session = Depends(get_db)):
    return [{"id": r.id, "code": r.code, "name_uz": r.name_uz, "name_ru": r.name_ru,
             "is_self_registrable": r.is_self_registrable, "permissions": sorted(p.code for p in r.permissions)}
            for r in db.scalars(select(Role).order_by(Role.id)).all()]


@router.get("/permissions", dependencies=[Depends(require("users.manage"))])
def permissions(db: Session = Depends(get_db)):
    return [{"code": p.code, "description": p.description} for p in db.scalars(select(Permission).order_by(Permission.code)).all()]


@router.put("/roles/{code}/permissions")
def set_role_permissions(code: str, body: RolePermissionsIn, admin: User = Depends(require("roles.manage")),
                         db: Session = Depends(get_db)):
    role = db.scalar(select(Role).where(Role.code == code))
    if not role:
        raise HTTPException(404, "Role not found")
    perms = db.scalars(select(Permission).where(Permission.code.in_(body.permission_codes))).all()
    if len(perms) != len(set(body.permission_codes)):
        raise HTTPException(422, "Unknown permission code")
    if role.code == "super_admin" and "roles.manage" not in body.permission_codes:
        raise HTTPException(422, "super_admin must keep roles.manage")
    role.permissions = list(perms)
    audit(db, admin, "set_permissions", "role", role.code, {"permissions": body.permission_codes})
    db.commit()
    return {"code": role.code, "permissions": sorted(p.code for p in role.permissions)}


@router.get("/organizations", dependencies=[Depends(require("users.manage"))])
def organizations(p: PageParams = Depends(), db: Session = Depends(get_db)):
    return paginate(db, select(Organization).order_by(Organization.id), p, lambda o: {
        "id": o.id, "name": o.name, "org_type": o.org_type, "tin": o.tin, "region_id": o.region_id,
        "is_simulated": o.is_simulated, "created_at": o.created_at})


# ---------- settings
@router.get("/settings", dependencies=[Depends(require("settings.manage"))])
def settings(db: Session = Depends(get_db)):
    return [{"key": s.key, "value": s.value, "description": s.description, "updated_at": s.updated_at}
            for s in db.scalars(select(PlatformSetting).order_by(PlatformSetting.key)).all()]


def _validate_setting(key: str, value) -> None:
    if key == "ranking.weights":
        if not isinstance(value, dict) or set(value) != {"price", "reliability", "freshness", "stock", "distance"}:
            raise HTTPException(422, "ranking.weights needs keys price, reliability, freshness, stock, distance")
        if any(not isinstance(v, (int, float)) or v < 0 for v in value.values()) or abs(sum(value.values()) - 1) > 0.001:
            raise HTTPException(422, "Weights must be non-negative and sum to 1")
    if key.startswith(("matching.", "analytics.", "freshness.", "ranking.max")) and not isinstance(value, (int, float)):
        raise HTTPException(422, "Value must be a number")


@router.put("/settings/{key}")
def put_setting(key: str, body: SettingIn, admin: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    _validate_setting(key, body.value)
    s = db.get(PlatformSetting, key)
    before = s.value if s else None
    if s is None:
        s = PlatformSetting(key=key, value=body.value, description=body.description)
        db.add(s)
    s.value = body.value
    if body.description is not None:
        s.description = body.description
    s.updated_by_id = admin.id
    audit(db, admin, "update", "setting", key, {"before": before, "after": body.value})
    db.commit()
    return {"key": s.key, "value": s.value, "description": s.description}


@router.get("/audit-logs", dependencies=[Depends(require("audit.view"))])
def audit_logs(entity_type: str | None = None, user_id: int | None = None, p: PageParams = Depends(),
               db: Session = Depends(get_db)):
    stmt = select(AuditLog)
    if entity_type:
        stmt = stmt.where(AuditLog.entity_type == entity_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    return paginate(db, stmt.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()), p, lambda a: {
        "id": a.id, "user_id": a.user_id, "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
        "changes": a.changes, "ip_address": a.ip_address, "created_at": a.created_at})


# ---------- categories & dynamic attributes
@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, admin: User = CAT, db: Session = Depends(get_db)):
    if db.scalar(select(Category).where(Category.slug == body.slug)):
        raise HTTPException(409, "Slug already exists")
    if body.parent_id and not db.get(Category, body.parent_id):
        raise HTTPException(422, "Unknown parent")
    c = Category(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, admin, "create", "category", c.id, {"slug": c.slug})
    db.commit()
    return category_out(c, True)


@router.put("/categories/{cid}")
def update_category(cid: int, body: CategoryIn, admin: User = CAT, db: Session = Depends(get_db)):
    c = get_or_404(db, Category, cid, "Category")
    if body.parent_id == cid:
        raise HTTPException(422, "A category cannot be its own parent")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    audit(db, admin, "update", "category", c.id, {"slug": c.slug, "is_active": c.is_active})
    db.commit()
    return category_out(c, True)


@router.post("/categories/{cid}/attributes", status_code=201)
def add_attribute(cid: int, body: CategoryAttributeIn, admin: User = CAT, db: Session = Depends(get_db)):
    c = get_or_404(db, Category, cid, "Category")
    if any(a.code == body.code for a in c.attributes):
        raise HTTPException(409, "Attribute code already exists in this category")
    if body.data_type in ("select", "multiselect") and not body.options:
        raise HTTPException(422, "Select attributes need options")
    a = CategoryAttribute(category_id=c.id, **body.model_dump(exclude={"options"}))
    a.options = [AttributeOption(**o.model_dump()) for o in body.options]
    db.add(a)
    db.flush()
    audit(db, admin, "create", "category_attribute", a.id, {"category": c.slug, "code": a.code})
    db.commit()
    return attribute_out(a)


@router.put("/attributes/{aid}")
def update_attribute(aid: int, body: CategoryAttributeIn, admin: User = CAT, db: Session = Depends(get_db)):
    a = get_or_404(db, CategoryAttribute, aid, "Attribute")
    for k, v in body.model_dump(exclude={"options"}).items():
        setattr(a, k, v)
    existing = {o.value: o for o in a.options}
    keep = []
    for o in body.options:
        opt = existing.get(o.value) or AttributeOption(value=o.value, label_uz=o.label_uz, label_ru=o.label_ru)
        opt.label_uz, opt.label_ru, opt.sort_order = o.label_uz, o.label_ru, o.sort_order
        keep.append(opt)
    a.options = keep
    audit(db, admin, "update", "category_attribute", a.id, {"code": a.code})
    db.commit()
    return attribute_out(a)


@router.delete("/attributes/{aid}", status_code=204)
def delete_attribute(aid: int, admin: User = CAT, db: Session = Depends(get_db)):
    a = get_or_404(db, CategoryAttribute, aid, "Attribute")
    audit(db, admin, "delete", "category_attribute", a.id, {"code": a.code})
    db.delete(a)
    db.commit()


# ---------- units, regions, districts, conversions, exchange rates
@router.post("/units", status_code=201)
def create_unit(body: UnitIn, admin: User = CAT, db: Session = Depends(get_db)):
    if db.scalar(select(Unit).where(Unit.code == body.code)):
        raise HTTPException(409, "Unit code exists")
    if body.dimension != "package" and body.factor_to_base is None:
        raise HTTPException(422, "factor_to_base is required for physical units")
    u = Unit(**body.model_dump())
    db.add(u)
    db.flush()
    audit(db, admin, "create", "unit", u.id, {"code": u.code})
    db.commit()
    return unit_out(u)


@router.put("/units/{uid}")
def update_unit(uid: int, body: UnitIn, admin: User = CAT, db: Session = Depends(get_db)):
    u = get_or_404(db, Unit, uid, "Unit")
    for k, v in body.model_dump().items():
        setattr(u, k, v)
    audit(db, admin, "update", "unit", u.id)
    db.commit()
    return unit_out(u)


@router.post("/unit-conversions", status_code=201)
def create_conversion(body: UnitConversionIn, admin: User = CAT, db: Session = Depends(get_db)):
    if body.from_unit_id == body.to_unit_id:
        raise HTTPException(422, "Units must differ")
    for uid in (body.from_unit_id, body.to_unit_id):
        get_or_404(db, Unit, uid, "Unit")
    if body.product_id:
        get_or_404(db, Product, body.product_id, "Product")
    c = UnitConversion(**body.model_dump())
    db.add(c)
    db.flush()
    audit(db, admin, "create", "unit_conversion", c.id, body.model_dump())
    db.commit()
    return {"id": c.id, **body.model_dump()}


@router.delete("/unit-conversions/{cid}", status_code=204)
def delete_conversion(cid: int, admin: User = CAT, db: Session = Depends(get_db)):
    c = get_or_404(db, UnitConversion, cid, "Conversion")
    db.delete(c)
    audit(db, admin, "delete", "unit_conversion", cid)
    db.commit()


@router.post("/regions", status_code=201)
def create_region(body: RegionIn, admin: User = CAT, db: Session = Depends(get_db)):
    if db.scalar(select(Region).where(Region.code == body.code)):
        raise HTTPException(409, "Region code exists")
    r = Region(**body.model_dump())
    db.add(r)
    db.flush()
    audit(db, admin, "create", "region", r.id)
    db.commit()
    return region_out(r)


@router.put("/regions/{rid}")
def update_region(rid: int, body: RegionIn, admin: User = CAT, db: Session = Depends(get_db)):
    r = get_or_404(db, Region, rid, "Region")
    for k, v in body.model_dump().items():
        setattr(r, k, v)
    audit(db, admin, "update", "region", r.id)
    db.commit()
    return region_out(r)


@router.post("/districts", status_code=201)
def create_district(body: DistrictIn, admin: User = CAT, db: Session = Depends(get_db)):
    get_or_404(db, Region, body.region_id, "Region")
    d = District(**body.model_dump())
    db.add(d)
    db.flush()
    audit(db, admin, "create", "district", d.id)
    db.commit()
    return {"id": d.id, **body.model_dump()}


@router.post("/exchange-rates", status_code=201)
def create_rate(body: ExchangeRateIn, admin: User = Depends(require("settings.manage")), db: Session = Depends(get_db)):
    if body.currency == "UZS":
        raise HTTPException(422, "UZS is the base currency")
    r = ExchangeRate(**body.model_dump())
    db.add(r)
    db.flush()
    audit(db, admin, "create", "exchange_rate", r.id, body.model_dump())
    db.commit()
    return {"id": r.id, **body.model_dump()}


@router.get("/subscription-plans", dependencies=[Depends(require("settings.manage"))])
def plans(db: Session = Depends(get_db)):
    return [{"id": p.id, "code": p.code, "name": p.name, "audience": p.audience, "features": p.features,
             "is_active": p.is_active} for p in db.scalars(select(SubscriptionPlan).order_by(SubscriptionPlan.id)).all()]


# ---------- simulated demo data
@router.get("/demo-data", dependencies=[Depends(require("demo.manage"))])
def demo_counts(db: Session = Depends(get_db)):
    def n(model):
        return db.scalar(select(func.count()).select_from(model).where(model.is_simulated.is_(True)))
    return {"products": n(Product), "suppliers": n(Supplier), "offers": n(Offer), "observations": n(PriceObservation),
            "manufacturers": n(Manufacturer), "organizations": n(Organization), "data_sources": n(DataSource)}


@router.delete("/demo-data")
def purge_demo(admin: User = Depends(require("demo.manage")), db: Session = Depends(get_db)):
    """Remove every record flagged is_simulated. Real data is untouched."""
    counts = demo_counts(db)
    sim_sup = select(Supplier.id).where(Supplier.is_simulated.is_(True))
    sim_prod = select(Product.id).where(Product.is_simulated.is_(True))
    db.execute(delete(QuoteRequest).where(QuoteRequest.supplier_id.in_(sim_sup) | QuoteRequest.product_id.in_(sim_prod)))
    db.execute(delete(SearchEvent).where(SearchEvent.query.startswith("demo:")))
    db.execute(delete(PriceObservation).where(PriceObservation.is_simulated.is_(True)))
    db.execute(delete(Offer).where(Offer.is_simulated.is_(True)))
    sim_products = select(Product.id).where(Product.is_simulated.is_(True))
    # keep simulated products that real records reference (shouldn't happen, but never break real data)
    real_refs = select(Offer.product_id).where(Offer.is_simulated.is_(False))
    real_obs = select(PriceObservation.product_id).where(PriceObservation.is_simulated.is_(False))
    db.execute(delete(Product).where(Product.id.in_(sim_products), Product.id.not_in(real_refs), Product.id.not_in(real_obs)))
    db.execute(delete(Supplier).where(Supplier.is_simulated.is_(True),
                                      Supplier.id.not_in(select(Offer.supplier_id).where(Offer.is_simulated.is_(False)))))
    db.execute(update(Product).where(Product.manufacturer_id.in_(select(Manufacturer.id).where(Manufacturer.is_simulated.is_(True))))
               .values(manufacturer_id=None))
    db.execute(delete(Manufacturer).where(Manufacturer.is_simulated.is_(True)))
    db.execute(update(DataSource).where(DataSource.is_simulated.is_(True)).values(is_active=False))
    audit(db, admin, "purge", "demo_data", None, counts)
    db.commit()
    return {"removed": counts}
