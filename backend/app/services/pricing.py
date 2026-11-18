"""Offer and price-observation writes. Every price change produces a new immutable observation."""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DataSource, Offer, PriceObservation, Product, Unit
from app.models.base import utcnow
from app.services.currency import to_uzs
from app.services.settings_service import get_setting
from app.services.units import try_conversion_factor


def normalize_price(db: Session, product: Product, unit: Unit, price_uzs: Decimal) -> tuple[Decimal | None, Decimal | None]:
    """Return (price per product base unit, base units per given unit) or (None, None) when not convertible."""
    factor = try_conversion_factor(db, unit, product.base_unit, product.id)
    if factor is None or factor == 0:
        return None, None
    per_base = (Decimal(price_uzs) / factor).quantize(Decimal("0.000001"), ROUND_HALF_UP)
    return per_base, factor


def quality_score(db: Session, *, has_supplier: bool, has_source_url: bool, unit_normalized: bool,
                  region_known: bool, match_confidence: float | None) -> tuple[Decimal, list[str]]:
    w = get_setting(db, "data_quality.weights")
    flags: list[str] = []
    score = 0.0
    if has_supplier:
        score += w["has_supplier"]
    else:
        flags.append("supplier_unknown")
    if has_source_url:
        score += w["has_source_url"]
    else:
        flags.append("no_source_url")
    if unit_normalized:
        score += w["unit_normalized"]
    else:
        flags.append("unit_not_normalizable")
    if region_known:
        score += w["region_known"]
    else:
        flags.append("region_unknown")
    mc = 1.0 if match_confidence is None else match_confidence
    score += w["match_confidence"] * mc
    if mc < 0.9:
        flags.append("uncertain_product_match")
    return Decimal(str(round(min(score, 1.0), 3))), flags


def record_observation(
    db: Session,
    *,
    product: Product,
    unit: Unit,
    price: Decimal,
    currency: str,
    region_id: int,
    price_type: str,
    data_source: DataSource,
    collection_method: str,
    observed_at: datetime | None = None,
    supplier_id: int | None = None,
    offer_id: int | None = None,
    source_url: str | None = None,
    original_product_name: str | None = None,
    original_unit_text: str | None = None,
    provenance_kind: str | None = None,
    match_confidence: float | None = None,
    collection_job_id: int | None = None,
    source_record_id: str | None = None,
    verification_status: str = "unverified",
    is_simulated: bool | None = None,
) -> PriceObservation:
    observed_at = observed_at or utcnow()
    price_uzs, rate, _ = to_uzs(db, price, currency, observed_at)
    per_base, _f = normalize_price(db, product, unit, price_uzs)
    q, flags = quality_score(db, has_supplier=supplier_id is not None, has_source_url=bool(source_url),
                             unit_normalized=per_base is not None, region_known=region_id is not None,
                             match_confidence=match_confidence)
    obs = PriceObservation(
        product_id=product.id, supplier_id=supplier_id, offer_id=offer_id,
        original_product_name=original_product_name or product.name,
        original_price=Decimal(price), original_currency=currency.upper(), original_unit_text=original_unit_text or unit.code,
        unit_id=unit.id, exchange_rate=rate, price_uzs=price_uzs,
        normalized_price_uzs=per_base, normalized_unit_id=product.base_unit_id if per_base is not None else None,
        region_id=region_id, price_type=price_type,
        provenance_kind=provenance_kind or data_source.default_provenance,
        data_source_id=data_source.id, collection_job_id=collection_job_id, collection_method=collection_method,
        source_url=source_url, source_record_id=source_record_id,
        observed_at=observed_at, collected_at=utcnow(), verification_status=verification_status,
        quality_score=q, confidence=Decimal(str(match_confidence)) if match_confidence is not None else None,
        quality_flags=flags, is_simulated=data_source.is_simulated if is_simulated is None else is_simulated,
    )
    db.add(obs)
    db.flush()
    return obs


def apply_offer_price(db: Session, offer: Offer, *, price: Decimal, currency: str, unit: Unit,
                      collection_method: str, observed_at: datetime | None = None) -> None:
    """Set the offer's price fields (with recorded conversion) and append a history observation."""
    product = offer.product or db.get(Product, offer.product_id)
    at = observed_at or utcnow()
    price_uzs, rate, rate_at = to_uzs(db, price, currency, at)
    per_base, factor = normalize_price(db, product, unit, price_uzs)
    offer.original_price = Decimal(price)
    offer.original_currency = currency.upper()
    offer.unit_id = unit.id
    offer.unit = unit
    offer.exchange_rate = rate
    offer.exchange_rate_at = rate_at
    offer.price_uzs = price_uzs
    offer.price_per_base_unit_uzs = per_base
    offer.units_per_offer_unit = factor
    offer.price_updated_at = at
    db.flush()
    ds = offer.data_source or db.get(DataSource, offer.data_source_id)
    record_observation(
        db, product=product, unit=unit, price=price, currency=currency, region_id=offer.region_id,
        price_type=offer.price_type, data_source=ds, collection_method=collection_method, observed_at=at,
        supplier_id=offer.supplier_id, offer_id=offer.id, source_url=offer.source_url,
        original_product_name=offer.original_product_name, provenance_kind=offer.provenance_kind,
        is_simulated=offer.is_simulated, verification_status=offer.verification_status,
    )


def find_duplicate_observation(db: Session, *, product_id: int, supplier_id: int | None, data_source_id: int,
                               price: Decimal, observed_at: datetime, region_id: int) -> PriceObservation | None:
    return db.scalar(select(PriceObservation).where(
        PriceObservation.product_id == product_id,
        PriceObservation.supplier_id == supplier_id if supplier_id else PriceObservation.supplier_id.is_(None),
        PriceObservation.data_source_id == data_source_id,
        PriceObservation.original_price == price,
        PriceObservation.observed_at == observed_at,
        PriceObservation.region_id == region_id,
    ).limit(1))
