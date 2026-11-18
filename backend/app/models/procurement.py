"""Buyer workflows, verification, ratings, notifications, audit and settings."""
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Money, Quantity, TimestampMixin, utcnow
from app.models.catalog import Product, Supplier


class QuoteRequest(Base, TimestampMixin):
    __tablename__ = "quote_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    buyer_organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    requested_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id"), index=True)
    quantity: Mapped[Decimal] = mapped_column(Quantity)
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    delivery_region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    message: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)  # open|answered|closed|cancelled

    product: Mapped[Product] = relationship(lazy="joined")
    supplier: Mapped[Supplier] = relationship(lazy="joined")
    responses: Mapped[list["QuoteResponse"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class QuoteResponse(Base):
    __tablename__ = "quote_responses"
    id: Mapped[int] = mapped_column(primary_key=True)
    quote_request_id: Mapped[int] = mapped_column(ForeignKey("quote_requests.id", ondelete="CASCADE"), index=True)
    responded_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    price: Mapped[Decimal] = mapped_column(Money)
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SavedProduct(Base):
    __tablename__ = "saved_products"
    __table_args__ = (UniqueConstraint("user_id", "product_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    product: Mapped[Product] = relationship(lazy="joined")


class SavedSupplier(Base):
    __tablename__ = "saved_suppliers"
    __table_args__ = (UniqueConstraint("user_id", "supplier_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    supplier: Mapped[Supplier] = relationship(lazy="joined")


class SupplierRating(Base):
    __tablename__ = "supplier_ratings"
    __table_args__ = (UniqueConstraint("supplier_id", "organization_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    score: Mapped[int] = mapped_column(Integer)  # 1..5
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VerificationRequest(Base, TimestampMixin):
    __tablename__ = "verification_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    target_type: Mapped[str] = mapped_column(String(30))  # supplier|offer|observation
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    requested_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    evidence: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)  # pending|approved|rejected
    reviewer_notes: Mapped[str | None] = mapped_column(Text)
    reviewed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SearchEvent(Base):
    """Search interest signal. Never presented as market demand."""

    __tablename__ = "search_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(String(300))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"), index=True)
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str | None] = mapped_column(Text)
    link: Mapped[str | None] = mapped_column(String(300))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(60), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(60))
    changes: Mapped[dict | None] = mapped_column(JSON)
    ip_address: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class PlatformSetting(Base):
    """Adjustable business rules (ranking weights, thresholds, freshness...) live here, not in code."""

    __tablename__ = "platform_settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

