"""Market data: sources, connectors, jobs, offers, price observations, matching."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Money, Quantity, Rate, TimestampMixin, UnitPrice, utcnow
from app.models.catalog import Product, Supplier
from app.models.reference import Region, Unit

# Provenance kinds — never mixed without labels.
PROVENANCE_KINDS = (
    "supplier_declared",
    "marketplace_listed",
    "official_statistic",
    "verified_transaction",
    "estimated",
    "simulated",
)
PRICE_TYPES = ("wholesale", "retail", "negotiated", "other")
VERIFICATION_STATUSES = ("unverified", "pending", "verified", "rejected")


class DataSource(Base, TimestampMixin):
    __tablename__ = "data_sources"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    source_type: Mapped[str] = mapped_column(String(30))
    # supplier_submission|marketplace|official_statistics|supplier_website|file_import|manual|api|simulated
    default_provenance: Mapped[str] = mapped_column(String(30))
    base_url: Mapped[str | None] = mapped_column(String(500))
    # Legal/technical review — integrations only run when 'permitted'.
    terms_status: Mapped[str] = mapped_column(String(20), default="unknown")  # unknown|pending_review|permitted|not_permitted
    has_public_api: Mapped[bool | None] = mapped_column(Boolean)
    requires_auth: Mapped[bool | None] = mapped_column(Boolean)
    redistribution_allowed: Mapped[bool | None] = mapped_column(Boolean)
    price_kind: Mapped[str | None] = mapped_column(String(30))  # wholesale|retail|mixed|statistical
    review_notes: Mapped[str | None] = mapped_column(Text)
    reliability_score: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.5"))  # 0..1
    freshness_hours: Mapped[int] = mapped_column(Integer, default=72)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class DataConnector(Base, TimestampMixin):
    __tablename__ = "data_connectors"
    id: Mapped[int] = mapped_column(primary_key=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    connector_type: Mapped[str] = mapped_column(String(50))  # key in the connector registry
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    interval_minutes: Mapped[int | None] = mapped_column(Integer)  # None => manual only
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    records_collected_total: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected_total: Mapped[int] = mapped_column(Integer, default=0)

    data_source: Mapped[DataSource] = relationship(lazy="joined")


class CollectionJob(Base):
    __tablename__ = "collection_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    connector_id: Mapped[int | None] = mapped_column(ForeignKey("data_connectors.id", ondelete="SET NULL"), index=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id", ondelete="CASCADE"), index=True)
    triggered_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    trigger: Mapped[str] = mapped_column(String(20), default="manual")  # manual|schedule|upload
    status: Mapped[str] = mapped_column(String(20), default="running")  # running|succeeded|partial|failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    records_seen: Mapped[int] = mapped_column(Integer, default=0)
    records_collected: Mapped[int] = mapped_column(Integer, default=0)
    records_rejected: Mapped[int] = mapped_column(Integer, default=0)
    records_pending_review: Mapped[int] = mapped_column(Integer, default=0)
    records_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)
    file_name: Mapped[str | None] = mapped_column(String(255))

    data_source: Mapped[DataSource] = relationship(lazy="joined")


class CollectionLog(Base):
    __tablename__ = "collection_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("collection_jobs.id", ondelete="CASCADE"), index=True)
    level: Mapped[str] = mapped_column(String(10))  # info|warning|error
    row_number: Mapped[int | None] = mapped_column(Integer)
    message: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Offer(Base, TimestampMixin):
    """Current offer state. Every create/price change also writes a PriceObservation (history)."""

    __tablename__ = "offers"
    __table_args__ = (Index("ix_offers_product_active", "product_id", "is_active"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    # As submitted
    original_price: Mapped[Decimal] = mapped_column(Money)
    original_currency: Mapped[str] = mapped_column(String(3), default="UZS")
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    # Conversion to UZS (recorded, never silent)
    exchange_rate: Mapped[Decimal | None] = mapped_column(Rate)
    exchange_rate_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_uzs: Mapped[Decimal] = mapped_column(Money)
    # Normalised to the product's base unit; null when units are not convertible
    price_per_base_unit_uzs: Mapped[Decimal | None] = mapped_column(UnitPrice)
    units_per_offer_unit: Mapped[Decimal | None] = mapped_column(Numeric(24, 9))  # offer unit in base units
    moq: Mapped[Decimal | None] = mapped_column(Quantity)  # in offer units
    available_qty: Mapped[Decimal | None] = mapped_column(Quantity)  # in offer units
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    location_id: Mapped[int | None] = mapped_column(ForeignKey("supplier_locations.id", ondelete="SET NULL"))
    delivery_available: Mapped[bool] = mapped_column(Boolean, default=False)
    delivery_cost_uzs: Mapped[Decimal | None] = mapped_column(Money)  # flat per order, if known
    delivery_regions: Mapped[list] = mapped_column(JSON, default=list)  # region ids served; [] = only own region
    other_fees_uzs: Mapped[Decimal | None] = mapped_column(Money)
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_type: Mapped[str] = mapped_column(String(20), default="wholesale", index=True)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    provenance_kind: Mapped[str] = mapped_column(String(30), default="supplier_declared")
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    source_url: Mapped[str | None] = mapped_column(String(1000))
    original_product_name: Mapped[str | None] = mapped_column(String(500))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=False)  # monetization-ready, shown as 'Sponsored'
    price_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    supplier: Mapped[Supplier] = relationship(lazy="joined")
    product: Mapped[Product] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined")
    region: Mapped[Region] = relationship(lazy="joined")
    data_source: Mapped[DataSource] = relationship(lazy="joined")


class PriceObservation(Base):
    """Immutable historical record. Never updated in place except verification/review fields."""

    __tablename__ = "price_observations"
    __table_args__ = (
        Index("ix_obs_product_time", "product_id", "observed_at"),
        Index("ix_obs_region_time", "region_id", "observed_at"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id", ondelete="SET NULL"), index=True)
    offer_id: Mapped[int | None] = mapped_column(ForeignKey("offers.id", ondelete="SET NULL"), index=True)
    original_product_name: Mapped[str | None] = mapped_column(String(500))
    original_price: Mapped[Decimal] = mapped_column(Money)
    original_currency: Mapped[str] = mapped_column(String(3))
    original_unit_text: Mapped[str | None] = mapped_column(String(60))
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    exchange_rate: Mapped[Decimal | None] = mapped_column(Rate)
    price_uzs: Mapped[Decimal] = mapped_column(Money)
    normalized_price_uzs: Mapped[Decimal | None] = mapped_column(UnitPrice)  # per product base unit
    normalized_unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"))
    price_type: Mapped[str] = mapped_column(String(20))
    provenance_kind: Mapped[str] = mapped_column(String(30), index=True)
    data_source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"), index=True)
    collection_job_id: Mapped[int | None] = mapped_column(ForeignKey("collection_jobs.id", ondelete="SET NULL"))
    collection_method: Mapped[str] = mapped_column(String(30))  # supplier_form|file_import|api|web|manual|seed
    source_url: Mapped[str | None] = mapped_column(String(1000))
    source_record_id: Mapped[str | None] = mapped_column(String(200))
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")
    quality_score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))  # 0..1
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))  # product match confidence
    quality_flags: Mapped[list] = mapped_column(JSON, default=list)
    is_outlier: Mapped[bool] = mapped_column(Boolean, default=False)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    product: Mapped[Product] = relationship(lazy="joined")
    unit: Mapped[Unit] = relationship(lazy="joined", foreign_keys=[unit_id])
    region: Mapped[Region] = relationship(lazy="joined")
    data_source: Mapped[DataSource] = relationship(lazy="joined")
    supplier: Mapped[Supplier | None] = relationship(lazy="joined")


class ProductMatch(Base, TimestampMixin):
    """Uncertain product matches held for human review — never auto-merged."""

    __tablename__ = "product_matches"
    id: Mapped[int] = mapped_column(primary_key=True)
    data_source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"))
    collection_job_id: Mapped[int | None] = mapped_column(ForeignKey("collection_jobs.id", ondelete="SET NULL"))
    original_name: Mapped[str] = mapped_column(String(500))
    candidate_product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    score: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    method: Mapped[str] = mapped_column(String(30))
    reasons: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|accepted|rejected
    raw_record: Mapped[dict] = mapped_column(JSON, default=dict)  # held row, replayed on accept
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    candidate_product: Mapped[Product | None] = relationship(lazy="joined")
