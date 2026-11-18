"""Products, manufacturers, suppliers and their locations."""
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin
from app.models.reference import Category, Region, Unit

supplier_categories = Table(
    "supplier_categories",
    Base.metadata,
    Column("supplier_id", ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True),
    Column("category_id", ForeignKey("categories.id", ondelete="CASCADE"), primary_key=True),
)


class Manufacturer(Base, TimestampMixin):
    __tablename__ = "manufacturers"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    country_code: Mapped[str | None] = mapped_column(String(2))
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"))
    website: Mapped[str | None] = mapped_column(String(255))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(300), index=True)
    normalized_name: Mapped[str] = mapped_column(String(300), index=True)
    search_terms: Mapped[list] = mapped_column(JSON, default=list)  # uz/ru/en synonyms
    description: Mapped[str | None] = mapped_column(Text)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), index=True)
    brand: Mapped[str | None] = mapped_column(String(150), index=True)
    model: Mapped[str | None] = mapped_column(String(150))
    manufacturer_id: Mapped[int | None] = mapped_column(ForeignKey("manufacturers.id", ondelete="SET NULL"), index=True)
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(50), index=True)
    base_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    country_of_origin: Mapped[str | None] = mapped_column(String(2))
    origin_type: Mapped[str] = mapped_column(String(20), default="unknown")  # domestic|import|unknown
    status: Mapped[str] = mapped_column(String(20), default="active")  # active|draft|archived|pending_review
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    category: Mapped[Category] = relationship(lazy="joined")
    manufacturer: Mapped[Manufacturer | None] = relationship(lazy="joined")
    base_unit: Mapped[Unit] = relationship(lazy="joined")
    attribute_values: Mapped[list["ProductAttributeValue"]] = relationship(
        back_populates="product", cascade="all, delete-orphan", lazy="selectin"
    )
    images: Mapped[list["ProductImage"]] = relationship(cascade="all, delete-orphan", lazy="selectin")


class ProductAttributeValue(Base):
    __tablename__ = "product_attributes"
    __table_args__ = (UniqueConstraint("product_id", "attribute_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    attribute_id: Mapped[int] = mapped_column(ForeignKey("category_attributes.id", ondelete="CASCADE"), index=True)
    value_text: Mapped[str | None] = mapped_column(Text)
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(24, 6))
    value_bool: Mapped[bool | None] = mapped_column(Boolean)
    value_json: Mapped[Any] = mapped_column(JSON, nullable=True)  # multiselect / dates as ISO strings

    product: Mapped[Product] = relationship(back_populates="attribute_values")


class ProductImage(Base):
    __tablename__ = "product_images"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    url: Mapped[str] = mapped_column(String(500))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class Supplier(Base, TimestampMixin):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(255))
    tin: Mapped[str | None] = mapped_column(String(20))
    supplier_type: Mapped[str] = mapped_column(String(30), index=True)  # manufacturer|wholesaler|distributor|importer|retail|other
    description: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    website: Mapped[str | None] = mapped_column(String(255))
    social_links: Mapped[dict] = mapped_column(JSON, default=dict)
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"), index=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    address: Mapped[str | None] = mapped_column(Text)
    # Registration != verification. Only an admin action sets 'verified'.
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified", index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    rating_avg: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    data_source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    region: Mapped[Region | None] = relationship(lazy="joined")
    categories: Mapped[list[Category]] = relationship(secondary=supplier_categories, lazy="selectin")
    locations: Mapped[list["SupplierLocation"]] = relationship(
        back_populates="supplier", cascade="all, delete-orphan", lazy="selectin"
    )


class SupplierLocation(Base):
    __tablename__ = "supplier_locations"
    id: Mapped[int] = mapped_column(primary_key=True)
    supplier_id: Mapped[int] = mapped_column(ForeignKey("suppliers.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(20), default="warehouse")  # warehouse|office|store|plant
    name: Mapped[str | None] = mapped_column(String(150))
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id"), index=True)
    district_id: Mapped[int | None] = mapped_column(ForeignKey("districts.id"))
    address: Mapped[str | None] = mapped_column(Text)
    # Only set when the supplier provided exact coordinates. Never fabricated.
    lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))

    supplier: Mapped[Supplier] = relationship(back_populates="locations")
    region: Mapped[Region] = relationship(lazy="joined")
