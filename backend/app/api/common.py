"""Shared helpers: pagination and serializers."""
from typing import Any

from fastapi import HTTPException, Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.models import (
    Category,
    CategoryAttribute,
    Offer,
    PriceObservation,
    Product,
    Region,
    Supplier,
    Unit,
    User,
)


class PageParams:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100)):
        self.page, self.page_size = page, page_size


def paginate(db: Session, stmt: Select, p: PageParams, mapper) -> dict[str, Any]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.scalars(stmt.offset((p.page - 1) * p.page_size).limit(p.page_size)).unique().all()
    return {"items": [mapper(r) for r in rows], "total": total, "page": p.page, "page_size": p.page_size}


def get_or_404(db: Session, model, id_: Any, name: str | None = None):
    obj = db.get(model, id_)
    if obj is None:
        raise HTTPException(404, f"{name or model.__name__} not found")
    return obj


def region_out(r: Region | None) -> dict | None:
    if r is None:
        return None
    return {"id": r.id, "code": r.code, "name_uz": r.name_uz, "name_ru": r.name_ru, "name_en": r.name_en,
            "aliases": r.aliases, "center_lat": r.center_lat, "center_lng": r.center_lng, "sort_order": r.sort_order}


def unit_out(u: Unit | None) -> dict | None:
    if u is None:
        return None
    return {"id": u.id, "code": u.code, "name_uz": u.name_uz, "name_ru": u.name_ru, "name_en": u.name_en,
            "symbol": u.symbol, "dimension": u.dimension, "factor_to_base": u.factor_to_base, "aliases": u.aliases}


def attribute_out(a: CategoryAttribute) -> dict:
    return {"id": a.id, "category_id": a.category_id, "code": a.code, "name_uz": a.name_uz, "name_ru": a.name_ru,
            "name_en": a.name_en, "data_type": a.data_type, "unit_id": a.unit_id, "is_required": a.is_required,
            "is_filterable": a.is_filterable, "is_matching_key": a.is_matching_key, "sort_order": a.sort_order,
            "options": [{"id": o.id, "value": o.value, "label_uz": o.label_uz, "label_ru": o.label_ru,
                         "sort_order": o.sort_order} for o in a.options]}


def category_out(c: Category, with_attributes: bool = False) -> dict:
    d = {"id": c.id, "parent_id": c.parent_id, "slug": c.slug, "name_uz": c.name_uz, "name_ru": c.name_ru,
         "name_en": c.name_en, "description": c.description, "icon": c.icon, "keywords": c.keywords,
         "is_active": c.is_active, "requires_compliance_note": c.requires_compliance_note,
         "compliance_note": c.compliance_note, "freshness_hours": c.freshness_hours, "sort_order": c.sort_order}
    if with_attributes:
        d["attributes"] = [attribute_out(a) for a in c.attributes]
    return d


def _attr_value(v) -> Any:
    if v.value_json is not None:
        return v.value_json
    if v.value_number is not None:
        return v.value_number
    if v.value_bool is not None:
        return v.value_bool
    return v.value_text


def product_out(p: Product, extra: dict | None = None) -> dict:
    d = {"id": p.id, "name": p.name, "description": p.description, "category_id": p.category_id,
         "category": {"id": p.category.id, "slug": p.category.slug, "name_uz": p.category.name_uz,
                      "name_ru": p.category.name_ru} if p.category else None,
         "brand": p.brand, "model": p.model, "manufacturer_id": p.manufacturer_id,
         "manufacturer": p.manufacturer.name if p.manufacturer else None,
         "sku": p.sku, "barcode": p.barcode, "base_unit": unit_out(p.base_unit),
         "country_of_origin": p.country_of_origin, "origin_type": p.origin_type, "status": p.status,
         "search_terms": p.search_terms, "is_simulated": p.is_simulated,
         "attributes": [{"attribute_id": v.attribute_id, "value": _attr_value(v)} for v in p.attribute_values],
         "images": [i.url for i in sorted(p.images, key=lambda i: i.sort_order)],
         "created_at": p.created_at, "updated_at": p.updated_at}
    if extra:
        d.update(extra)
    return d


def supplier_out(s: Supplier, detail: bool = False) -> dict:
    d = {"id": s.id, "name": s.name, "supplier_type": s.supplier_type, "region": region_out(s.region),
         "verification_status": s.verification_status, "verified_at": s.verified_at,
         "rating_avg": s.rating_avg, "rating_count": s.rating_count, "is_simulated": s.is_simulated,
         "organization_id": s.organization_id, "categories": [{"id": c.id, "slug": c.slug, "name_uz": c.name_uz,
                                                                "name_ru": c.name_ru} for c in s.categories],
         "description": s.description, "website": s.website, "is_active": s.is_active}
    if detail:
        d.update({"legal_name": s.legal_name, "tin": s.tin, "phone": s.phone, "email": s.email,
                  "social_links": s.social_links, "district_id": s.district_id, "address": s.address,
                  "data_source_id": s.data_source_id, "created_at": s.created_at,
                  "locations": [{"id": l.id, "kind": l.kind, "name": l.name, "region": region_out(l.region),
                                 "district_id": l.district_id, "address": l.address, "lat": l.lat, "lng": l.lng}
                                for l in s.locations]})
    return d


def offer_out(o: Offer) -> dict:
    return {"id": o.id, "supplier": {"id": o.supplier.id, "name": o.supplier.name,
                                     "verification_status": o.supplier.verification_status,
                                     "is_simulated": o.supplier.is_simulated},
            "product": {"id": o.product.id, "name": o.product.name, "category_id": o.product.category_id,
                        "base_unit": o.product.base_unit.code},
            "original_price": o.original_price, "original_currency": o.original_currency,
            "exchange_rate": o.exchange_rate, "exchange_rate_at": o.exchange_rate_at,
            "price_uzs": o.price_uzs, "price_per_base_unit_uzs": o.price_per_base_unit_uzs,
            "unit": unit_out(o.unit), "moq": o.moq, "available_qty": o.available_qty, "region": region_out(o.region),
            "district_id": o.district_id, "location_id": o.location_id,
            "delivery_available": o.delivery_available, "delivery_cost_uzs": o.delivery_cost_uzs,
            "delivery_regions": o.delivery_regions, "other_fees_uzs": o.other_fees_uzs,
            "valid_from": o.valid_from, "valid_until": o.valid_until, "price_type": o.price_type,
            "verification_status": o.verification_status, "provenance_kind": o.provenance_kind,
            "data_source": {"id": o.data_source.id, "name": o.data_source.name, "code": o.data_source.code},
            "source_url": o.source_url, "original_product_name": o.original_product_name,
            "is_active": o.is_active, "is_simulated": o.is_simulated, "is_featured": o.is_featured,
            "price_updated_at": o.price_updated_at, "created_at": o.created_at, "updated_at": o.updated_at}


def observation_out(o: PriceObservation) -> dict:
    return {"id": o.id, "product_id": o.product_id, "product_name": o.product.name if o.product else None,
            "supplier_id": o.supplier_id, "supplier_name": o.supplier.name if o.supplier else None,
            "offer_id": o.offer_id, "original_product_name": o.original_product_name,
            "original_price": o.original_price, "original_currency": o.original_currency,
            "original_unit_text": o.original_unit_text, "unit": o.unit.code if o.unit else None,
            "exchange_rate": o.exchange_rate, "price_uzs": o.price_uzs, "normalized_price_uzs": o.normalized_price_uzs,
            "region": region_out(o.region), "price_type": o.price_type, "provenance_kind": o.provenance_kind,
            "data_source": {"id": o.data_source.id, "name": o.data_source.name} if o.data_source else None,
            "collection_method": o.collection_method, "collection_job_id": o.collection_job_id,
            "source_url": o.source_url, "observed_at": o.observed_at, "collected_at": o.collected_at,
            "verification_status": o.verification_status, "quality_score": o.quality_score,
            "confidence": o.confidence, "quality_flags": o.quality_flags, "is_outlier": o.is_outlier,
            "is_simulated": o.is_simulated}


def user_out(u: User) -> dict:
    return {"id": u.id, "email": u.email, "full_name": u.full_name, "phone": u.phone, "locale": u.locale,
            "is_active": u.is_active, "role": u.role.code if u.role else None,
            "role_name": {"uz": u.role.name_uz, "ru": u.role.name_ru} if u.role else None,
            "permissions": sorted(u.permission_codes), "created_at": u.created_at, "last_login_at": u.last_login_at,
            "organizations": [{"id": m.organization.id, "name": m.organization.name, "org_type": m.organization.org_type,
                               "member_role": m.member_role} for m in u.memberships]}
