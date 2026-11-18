"""Shared ingestion pipeline: validate → match → normalize → dedupe → score → store (with provenance)."""
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import (
    PRICE_TYPES,
    Category,
    CollectionJob,
    CollectionLog,
    DataConnector,
    DataSource,
    Offer,
    Product,
    ProductMatch,
    Region,
    Supplier,
    User,
)
from app.models.base import utcnow
from app.services.currency import MissingExchangeRate
from app.services.market_data.base import ConnectorError, RawRecord, get_connector_class
from app.services.matching import find_matches
from app.services.pricing import apply_offer_price, find_duplicate_observation, record_observation
from app.services.settings_service import get_setting
from app.services.text import normalize_text
from app.services.units import resolve_unit

SUPPLIER_TYPES = ("manufacturer", "wholesaler", "distributor", "importer", "retail", "other")


class RowError(ValueError):
    pass


@dataclass
class IngestResult:
    status: str  # stored | duplicate | pending_review | rejected
    message: str = ""
    observation_id: int | None = None
    offer_id: int | None = None
    flags: list[str] = field(default_factory=list)


def _dec(v: Any, name: str, required: bool = False) -> Decimal | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        if required:
            raise RowError(f"{name} is required")
        return None
    try:
        d = Decimal(str(v).replace(" ", "").replace(" ", "").replace(",", "."))
    except InvalidOperation:
        raise RowError(f"{name} is not a number: {v!r}")
    if d < 0:
        raise RowError(f"{name} must not be negative")
    return d


def _dt(v: Any) -> datetime | None:
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    if isinstance(v, date):
        return datetime(v.year, v.month, v.day, tzinfo=timezone.utc)
    s = str(v).strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d.%m.%Y", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    try:
        d = datetime.fromisoformat(s)
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        raise RowError(f"Unrecognised date: {v!r}")


def _bool(v: Any) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "ha", "да", "y")


def resolve_region(db: Session, text: Any) -> Region | None:
    if text in (None, ""):
        return None
    t = normalize_text(str(text))
    for r in db.scalars(select(Region)).all():
        names = {r.code.lower(), normalize_text(r.name_uz), normalize_text(r.name_ru), normalize_text(r.name_en)}
        names |= {normalize_text(a) for a in (r.aliases or [])}
        if t in names:
            return r
    return None


def _resolve_category(db: Session, text: Any) -> Category | None:
    if text in (None, ""):
        return None
    t = normalize_text(str(text))
    for c in db.scalars(select(Category)).all():
        if t in {c.slug.lower(), normalize_text(c.name_uz), normalize_text(c.name_ru), normalize_text(c.name_en or "")}:
            return c
    return None


def _resolve_supplier(db: Session, rec: RawRecord, region: Region, source: DataSource) -> Supplier | None:
    name = (rec.get("supplier_name") or "").strip()
    tin = str(rec.get("supplier_tin") or "").strip() or None
    if not name and not tin:
        return None
    sup = None
    if tin:
        sup = db.scalar(select(Supplier).where(Supplier.tin == tin))
    if sup is None and name:
        sup = db.scalar(select(Supplier).where(func.lower(Supplier.name) == name.lower()))
    if sup is None:
        stype = (rec.get("supplier_type") or "other").lower()
        sup = Supplier(name=name or f"TIN {tin}", tin=tin, supplier_type=stype if stype in SUPPLIER_TYPES else "other",
                       region_id=region.id, verification_status="unverified", data_source_id=source.id,
                       is_simulated=source.is_simulated)
        db.add(sup)
        db.flush()
    return sup


def ingest_record(db: Session, *, source: DataSource, rec: RawRecord, job: CollectionJob | None = None,
                  collection_method: str = "file_import", default_record_type: str = "observation",
                  allow_create_products: bool = False, forced_product_id: int | None = None) -> IngestResult:
    name = (rec.get("product_name") or "").strip()
    if not name:
        raise RowError("product_name is required")
    price = _dec(rec.get("price"), "price", required=True)
    if price == 0:
        raise RowError("price must be greater than zero")
    currency = (rec.get("currency") or "UZS").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise RowError(f"Invalid currency: {currency!r}")
    unit = resolve_unit(db, str(rec.get("unit") or ""))
    if unit is None:
        raise RowError(f"Unknown unit: {rec.get('unit')!r}")
    region = resolve_region(db, rec.get("region"))
    if region is None:
        raise RowError(f"Unknown or missing Uzbekistan region: {rec.get('region')!r}")
    price_type = (rec.get("price_type") or "wholesale").strip().lower()
    if price_type not in PRICE_TYPES:
        raise RowError(f"Invalid price_type: {price_type!r}")
    observed_at = _dt(rec.get("observed_at")) or utcnow()
    if observed_at > utcnow():
        raise RowError("observed_at is in the future")
    record_type = (rec.get("record_type") or default_record_type).strip().lower()

    # --- product matching
    confidence: float | None = None
    product: Product | None = None
    category = _resolve_category(db, rec.get("category"))
    if forced_product_id:
        product = db.get(Product, forced_product_id)
        confidence = 1.0  # human-confirmed
    else:
        matches = find_matches(db, name, barcode=str(rec.get("barcode") or "") or None, sku=rec.get("sku") or None,
                               brand=rec.get("brand") or None, category_id=category.id if category else None)
        auto = float(get_setting(db, "matching.auto_accept_threshold"))
        review = float(get_setting(db, "matching.review_threshold"))
        top = matches[0] if matches else None
        if top and top.score >= auto:
            product, confidence = top.product, top.score
        elif top and top.score >= review:
            pm = ProductMatch(data_source_id=source.id, collection_job_id=job.id if job else None, original_name=name,
                              candidate_product_id=top.product.id, score=Decimal(str(top.score)), method=top.method,
                              reasons=top.reasons, raw_record=_jsonable(rec))
            db.add(pm)
            return IngestResult("pending_review", f"Uncertain match to '{top.product.name}' ({top.score:.2f}); held for review")
        elif allow_create_products and category:
            product = Product(name=name, normalized_name=normalize_text(name), category_id=category.id,
                              brand=rec.get("brand") or None, sku=rec.get("sku") or None,
                              barcode=str(rec.get("barcode") or "") or None, base_unit_id=unit.id,
                              status="active", is_simulated=source.is_simulated)
            db.add(product)
            db.flush()
            confidence = 1.0
        else:
            pm = ProductMatch(data_source_id=source.id, collection_job_id=job.id if job else None, original_name=name,
                              candidate_product_id=top.product.id if top else None,
                              score=Decimal(str(top.score)) if top else None, method=top.method if top else "none",
                              reasons=(top.reasons if top else []) + ["No confident match; needs a product"],
                              raw_record=_jsonable(rec))
            db.add(pm)
            return IngestResult("pending_review", "No matching product; held for review")
    if product is None:
        raise RowError("Product not found")

    supplier = _resolve_supplier(db, rec, region, source)

    # --- duplicates
    dup = find_duplicate_observation(db, product_id=product.id, supplier_id=supplier.id if supplier else None,
                                     data_source_id=source.id, price=price, observed_at=observed_at, region_id=region.id)
    if dup:
        return IngestResult("duplicate", "Identical observation already stored", observation_id=dup.id)

    try:
        if record_type == "offer" and supplier:
            offer = db.scalar(select(Offer).where(Offer.supplier_id == supplier.id, Offer.product_id == product.id,
                                                  Offer.region_id == region.id, Offer.price_type == price_type))
            if offer is None:
                offer = Offer(supplier_id=supplier.id, product_id=product.id, region_id=region.id, price_type=price_type,
                              original_price=price, original_currency=currency, unit_id=unit.id, price_uzs=price,
                              data_source_id=source.id, provenance_kind=source.default_provenance,
                              is_simulated=source.is_simulated, original_product_name=name)
                db.add(offer)
                db.flush()
            offer.moq = _dec(rec.get("moq"), "moq")
            offer.available_qty = _dec(rec.get("available_qty"), "available_qty")
            if rec.get("delivery_available") not in (None, ""):
                offer.delivery_available = _bool(rec.get("delivery_available"))
            offer.delivery_cost_uzs = _dec(rec.get("delivery_cost"), "delivery_cost")
            offer.valid_until = _dt(rec.get("valid_until"))
            offer.source_url = rec.get("source_url") or offer.source_url
            offer.is_active = True
            offer.product, offer.data_source = product, source
            apply_offer_price(db, offer, price=price, currency=currency, unit=unit,
                              collection_method=collection_method, observed_at=observed_at)
            return IngestResult("stored", "Offer upserted", offer_id=offer.id)
        obs = record_observation(
            db, product=product, unit=unit, price=price, currency=currency, region_id=region.id, price_type=price_type,
            data_source=source, collection_method=collection_method, observed_at=observed_at,
            supplier_id=supplier.id if supplier else None, source_url=rec.get("source_url") or None,
            original_product_name=name, original_unit_text=str(rec.get("unit")), match_confidence=confidence,
            collection_job_id=job.id if job else None,
        )
        return IngestResult("stored", "Observation stored", observation_id=obs.id, flags=obs.quality_flags)
    except MissingExchangeRate as e:
        raise RowError(str(e))


def _jsonable(rec: RawRecord) -> dict:
    out = {}
    for k, v in rec.items():
        if isinstance(v, (datetime, date)):
            out[k] = v.isoformat()
        elif isinstance(v, Decimal):
            out[k] = str(v)
        else:
            out[k] = v
    return out


def run_collection(db: Session, *, source: DataSource, connector: DataConnector | None, user: User | None,
                   trigger: str = "manual", file_name: str | None = None, **collect_kwargs: Any) -> CollectionJob:
    """Run a connector end-to-end, row by row with savepoints so one bad row never aborts the job."""
    job = CollectionJob(connector_id=connector.id if connector else None, data_source_id=source.id,
                        triggered_by_id=user.id if user else None, trigger=trigger, file_name=file_name)
    db.add(job)
    db.flush()
    type_key = connector.connector_type if connector else "file_import"
    cfg = (connector.config if connector else {}) or {}
    try:
        cls = get_connector_class(type_key)
        records = list(cls(connector, source).collect(**collect_kwargs))
    except ConnectorError as e:
        job.status, job.error, job.finished_at = "failed", str(e), utcnow()
        db.add(CollectionLog(job_id=job.id, level="error", message=str(e)))
        if connector:
            connector.last_run_at = connector.last_failure_at = utcnow()
            connector.last_error = str(e)
        db.commit()
        return job

    method = {"file_import": "file_import", "http_json": "api", "manual_entry": "manual"}.get(type_key, type_key)
    for i, rec in enumerate(records, start=2 if type_key == "file_import" else 1):
        job.records_seen += 1
        sp = db.begin_nested()
        try:
            res = ingest_record(db, source=source, rec=rec, job=job, collection_method=method,
                                default_record_type=collect_kwargs.get("record_type") or cfg.get("default_record_type", "observation"),
                                allow_create_products=bool(collect_kwargs.get("allow_create_products", cfg.get("allow_create_products", False))))
            sp.commit()
            if res.status == "stored":
                job.records_collected += 1
            elif res.status == "duplicate":
                job.records_duplicate += 1
            elif res.status == "pending_review":
                job.records_pending_review += 1
            if res.status != "stored":
                db.add(CollectionLog(job_id=job.id, level="info", row_number=i, message=res.message))
        except (RowError, ValueError) as e:
            sp.rollback()
            job.records_rejected += 1
            db.add(CollectionLog(job_id=job.id, level="warning", row_number=i, message=str(e), payload=_jsonable(rec)))
    job.finished_at = utcnow()
    job.status = "succeeded" if job.records_rejected == 0 else ("partial" if job.records_collected else "failed")
    if connector:
        connector.last_run_at = utcnow()
        connector.records_collected_total += job.records_collected
        connector.records_rejected_total += job.records_rejected
        if job.status == "failed":
            connector.last_failure_at = utcnow()
            connector.last_error = f"{job.records_rejected} rows rejected"
        else:
            connector.last_success_at = utcnow()
            connector.last_error = None
    db.commit()
    return job
