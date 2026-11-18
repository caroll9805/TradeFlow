"""Deterministic offer comparison and total procurement cost.

No LLM is involved here. Every recommendation is returned with the exact criteria,
the per-criterion scores and the weights used (weights are admin-configurable)."""
import math
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Offer, Product, Region
from app.models.base import utcnow
from app.services.geo import aware, region_distance_km
from app.services.settings_service import get_setting

Q2 = Decimal("0.01")
VERIFICATION_RELIABILITY = {"verified": 1.0, "pending": 0.6, "unverified": 0.4, "rejected": 0.0}


@dataclass
class CompareParams:
    product_id: int
    quantity: Decimal | None = None  # in product base units
    region_id: int | None = None  # only offers located in this region
    buyer_region_id: int | None = None  # delivery destination, for distance & delivery checks
    price_type: str | None = None
    verified_only: bool = False
    include_simulated: bool = True


def _freshness_threshold_hours(db: Session, offer: Offer) -> int:
    cat = offer.product.category
    if cat and cat.freshness_hours:
        return cat.freshness_hours
    if offer.data_source and offer.data_source.freshness_hours:
        return offer.data_source.freshness_hours
    return int(get_setting(db, "freshness.default_hours"))


def compare_offers(db: Session, p: CompareParams) -> dict:
    product = db.get(Product, p.product_id)
    if product is None:
        raise LookupError("Product not found")
    weights: dict = get_setting(db, "ranking.weights")
    max_km = float(get_setting(db, "ranking.max_distance_km"))
    now = utcnow()

    q = select(Offer).where(Offer.product_id == p.product_id, Offer.is_active.is_(True))
    if p.region_id:
        q = q.where(Offer.region_id == p.region_id)
    if p.price_type:
        q = q.where(Offer.price_type == p.price_type)
    if not p.include_simulated:
        q = q.where(Offer.is_simulated.is_(False))
    offers = db.scalars(q).unique().all()
    buyer_region = db.get(Region, p.buyer_region_id) if p.buyer_region_id else None

    rows: list[dict] = []
    for o in offers:
        notes: list[str] = []
        excluded: str | None = None
        if p.verified_only and o.supplier.verification_status != "verified":
            continue
        valid_until = aware(o.valid_until)
        if valid_until and valid_until < now:
            excluded = "offer_expired"
        if o.price_per_base_unit_uzs is None:
            excluded = excluded or "unit_not_comparable"

        upo = Decimal(o.units_per_offer_unit) if o.units_per_offer_unit else None  # base units per offer unit
        unit_price = Decimal(o.price_uzs)
        order_units = goods = delivery = fees = total = effective = None
        stock_status = "unknown"
        deliverable = True
        if upo and p.quantity:
            needed = Decimal(p.quantity) / upo
            if o.unit.dimension in ("count", "package"):
                needed = Decimal(math.ceil(needed))
            order_units = needed
            if o.moq and Decimal(o.moq) > needed:
                order_units = Decimal(o.moq)
                notes.append("moq_applied")
            goods = (order_units * unit_price).quantize(Q2, ROUND_HALF_UP)
            if o.available_qty is not None:
                stock_status = "sufficient" if Decimal(o.available_qty) >= order_units else "insufficient"
        elif o.available_qty is not None:
            stock_status = "declared"

        # Delivery: only declared costs are added; unknown costs are flagged, never invented.
        delivery_known = True
        if buyer_region and buyer_region.id != o.region_id:
            serves = o.delivery_available and (not o.delivery_regions or buyer_region.id in o.delivery_regions)
            if not serves:
                deliverable = False
                notes.append("no_delivery_to_buyer_region")
            elif o.delivery_cost_uzs is None:
                delivery_known = False
                notes.append("delivery_cost_unknown")
        if o.delivery_available and o.delivery_cost_uzs is not None and deliverable:
            delivery = Decimal(o.delivery_cost_uzs)
        if o.other_fees_uzs is not None:
            fees = Decimal(o.other_fees_uzs)
        if goods is not None:
            total = goods + (delivery or 0) + (fees or 0)
            effective = (total / Decimal(p.quantity)).quantize(Decimal("0.000001"), ROUND_HALF_UP)

        # Criteria
        age_h = (now - aware(o.price_updated_at)).total_seconds() / 3600
        thr = _freshness_threshold_hours(db, o)
        freshness = max(0.0, 1.0 - age_h / (2 * thr))
        if age_h > thr:
            notes.append("stale")
        ver = VERIFICATION_RELIABILITY.get(o.supplier.verification_status, 0.4)
        src_rel = float(o.data_source.reliability_score or 0.5)
        rating = float(o.supplier.rating_avg) / 5 if o.supplier.rating_avg is not None else 0.5
        reliability = 0.5 * ver + 0.3 * src_rel + 0.2 * rating
        dist = region_distance_km(o.region, buyer_region)
        distance_score = 1.0 if dist is None else max(0.0, 1.0 - dist / max_km)
        stock_score = {"sufficient": 1.0, "declared": 0.8, "unknown": 0.5, "insufficient": 0.0}[stock_status]

        rows.append({
            "offer_id": o.id,
            "supplier": {"id": o.supplier.id, "name": o.supplier.name, "type": o.supplier.supplier_type,
                          "verification_status": o.supplier.verification_status,
                          "rating_avg": o.supplier.rating_avg, "rating_count": o.supplier.rating_count,
                          "is_simulated": o.supplier.is_simulated},
            "region": {"id": o.region.id, "code": o.region.code, "name_uz": o.region.name_uz, "name_ru": o.region.name_ru},
            "price": {"original": o.original_price, "currency": o.original_currency, "unit": o.unit.code,
                       "exchange_rate": o.exchange_rate, "exchange_rate_at": o.exchange_rate_at,
                       "price_uzs": o.price_uzs, "per_base_unit_uzs": o.price_per_base_unit_uzs,
                       "base_unit": product.base_unit.code, "price_type": o.price_type},
            "moq": o.moq, "available_qty": o.available_qty, "stock_status": stock_status,
            "available_base_units": (Decimal(o.available_qty) * upo) if (o.available_qty is not None and upo) else None,
            "delivery": {"available": o.delivery_available, "cost_uzs": o.delivery_cost_uzs,
                          "deliverable_to_buyer": deliverable, "cost_known": delivery_known,
                          "distance_km": None if dist is None else round(dist, 1)},
            "cost": {"order_units": order_units, "goods_uzs": goods, "delivery_uzs": delivery, "fees_uzs": fees,
                      "total_uzs": total, "effective_per_base_unit_uzs": effective},
            "freshness": {"price_updated_at": o.price_updated_at, "age_hours": round(age_h, 1), "threshold_hours": thr},
            "provenance": {"kind": o.provenance_kind, "source": o.data_source.name, "source_id": o.data_source_id,
                            "source_url": o.source_url, "verification_status": o.verification_status,
                            "is_simulated": o.is_simulated, "original_product_name": o.original_product_name},
            "is_featured": o.is_featured,
            "notes": notes,
            "excluded_reason": excluded,
            "_criteria": {"reliability": reliability, "freshness": freshness, "distance": distance_score, "stock": stock_score},
            "_comparable": effective if effective is not None else o.price_per_base_unit_uzs,
            "_eligible": excluded is None and stock_status != "insufficient" and deliverable and (total is None or delivery_known),
        })

    comparable = [r for r in rows if r["excluded_reason"] is None and r["_comparable"] is not None]
    min_cost = min((Decimal(r["_comparable"]) for r in comparable), default=None)
    for r in rows:
        c = r.pop("_criteria")
        price_score = float(min_cost / Decimal(r["_comparable"])) if (min_cost and r["_comparable"]) else 0.0
        crit = {"price": price_score, **c}
        breakdown = [{"criterion": k, "score": round(v, 4), "weight": weights.get(k, 0),
                      "contribution": round(v * weights.get(k, 0), 4)} for k, v in crit.items()]
        r["score"] = round(sum(b["contribution"] for b in breakdown), 4) if r["excluded_reason"] is None else None
        r["score_breakdown"] = breakdown

    cheapest = min(comparable, key=lambda r: Decimal(r["_comparable"]), default=None)
    eligible = [r for r in rows if r["_eligible"] and r["score"] is not None]
    best = max(eligible, key=lambda r: r["score"], default=None)

    for r in rows:
        r["comparable_cost_uzs"] = r.pop("_comparable")
        r["eligible_for_best"] = r.pop("_eligible")
    rows.sort(key=lambda r: (r["score"] is None, -(r["score"] or 0)))

    per_unit = [Decimal(r["price"]["per_base_unit_uzs"]) for r in comparable]
    summary = {
        "offers_total": len(rows),
        "offers_comparable": len(comparable),
        "min_per_base_unit_uzs": min(per_unit) if per_unit else None,
        "max_per_base_unit_uzs": max(per_unit) if per_unit else None,
        "avg_per_base_unit_uzs": (sum(per_unit) / len(per_unit)).quantize(Q2) if per_unit else None,
        "base_unit": product.base_unit.code,
        "simulated_offers": sum(1 for r in rows if r["provenance"]["is_simulated"]),
    }
    explanation = _explain(best, cheapest, weights, p)
    return {
        "product": {"id": product.id, "name": product.name, "base_unit": product.base_unit.code},
        "params": {"quantity": p.quantity, "region_id": p.region_id, "buyer_region_id": p.buyer_region_id,
                    "price_type": p.price_type},
        "weights": weights,
        "summary": summary,
        "cheapest_offer_id": cheapest["offer_id"] if cheapest else None,
        "best_offer_id": best["offer_id"] if best else None,
        "explanation": explanation,
        "offers": rows,
    }


def _explain(best: dict | None, cheapest: dict | None, weights: dict, p: CompareParams) -> list[str]:
    out: list[str] = []
    if not best and not cheapest:
        return ["No comparable offers for the selected filters."]
    basis = "total procurement cost per base unit" if p.quantity else "price per base unit (enter a quantity to include MOQ, delivery and fees)"
    out.append(f"Cheapest is ranked by {basis}.")
    out.append("Best overall = weighted score of " + ", ".join(f"{k} {int(v * 100)}%" for k, v in weights.items()) + ".")
    if best and cheapest and best["offer_id"] != cheapest["offer_id"]:
        out.append(
            f"Best overall ({best['supplier']['name']}) differs from cheapest ({cheapest['supplier']['name']}) because "
            "of higher reliability, freshness, stock coverage or proximity — see the score breakdown."
        )
    if cheapest and not cheapest["eligible_for_best"]:
        out.append("The cheapest offer is not eligible for 'best overall' (insufficient stock, no delivery or unknown delivery cost).")
    return out


def regional_prices(db: Session, product_id: int, include_simulated: bool = True) -> list[dict]:
    q = select(Offer).where(Offer.product_id == product_id, Offer.is_active.is_(True),
                            Offer.price_per_base_unit_uzs.is_not(None))
    if not include_simulated:
        q = q.where(Offer.is_simulated.is_(False))
    by_region: dict[int, list[Offer]] = {}
    for o in db.scalars(q).unique().all():
        by_region.setdefault(o.region_id, []).append(o)
    out = []
    for rid, os_ in by_region.items():
        vals = [Decimal(o.price_per_base_unit_uzs) for o in os_]
        r = os_[0].region
        out.append({"region_id": rid, "code": r.code, "name_uz": r.name_uz, "name_ru": r.name_ru,
                    "center_lat": r.center_lat, "center_lng": r.center_lng,
                    "offers": len(vals), "suppliers": len({o.supplier_id for o in os_}),
                    "min": min(vals), "max": max(vals), "avg": (sum(vals) / len(vals)).quantize(Q2)})
    out.sort(key=lambda x: x["avg"])
    return out
