"""Geography, units, categories and dynamic attributes — all configurable data."""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import Rate, TimestampMixin


class Region(Base):
    __tablename__ = "regions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # e.g. UZ-TK
    name_uz: Mapped[str] = mapped_column(String(120))
    name_ru: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str] = mapped_column(String(120))
    aliases: Mapped[list] = mapped_column(JSON, default=list)  # alternative spellings for search/AI
    # Approximate administrative-centre point; used for region-level map markers and distance.
    center_lat: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    center_lng: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    districts: Mapped[list["District"]] = relationship(back_populates="region")


class District(Base):
    __tablename__ = "districts"
    id: Mapped[int] = mapped_column(primary_key=True)
    region_id: Mapped[int] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), index=True)
    name_uz: Mapped[str] = mapped_column(String(120))
    name_ru: Mapped[str] = mapped_column(String(120))
    region: Mapped[Region] = relationship(back_populates="districts")


class Unit(Base):
    """Units belong to a dimension. Conversion inside a dimension uses factor_to_base.
    Package-type units (box, pallet, set) have dimension 'package' and need a product-specific
    UnitConversion to be comparable."""

    __tablename__ = "units"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name_uz: Mapped[str] = mapped_column(String(60))
    name_ru: Mapped[str] = mapped_column(String(60))
    name_en: Mapped[str] = mapped_column(String(60))
    symbol: Mapped[str] = mapped_column(String(20))
    dimension: Mapped[str] = mapped_column(String(20), index=True)  # mass|volume|length|area|count|package
    factor_to_base: Mapped[Decimal | None] = mapped_column(Numeric(24, 9))  # null for package units
    aliases: Mapped[list] = mapped_column(JSON, default=list)  # "кг", "kg", "kilo" ...


class UnitConversion(Base):
    """Product-specific conversions, e.g. 1 box of product X = 12 pieces; 1 bag cement = 50 kg."""

    __tablename__ = "unit_conversions"
    __table_args__ = (UniqueConstraint("product_id", "from_unit_id", "to_unit_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"), index=True)
    from_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    to_unit_id: Mapped[int] = mapped_column(ForeignKey("units.id"))
    factor: Mapped[Decimal] = mapped_column(Numeric(24, 9))  # 1 from_unit = factor to_unit


class Category(Base, TimestampMixin):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id", ondelete="SET NULL"), index=True)
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name_uz: Mapped[str] = mapped_column(String(150))
    name_ru: Mapped[str] = mapped_column(String(150))
    name_en: Mapped[str | None] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(50))
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    requires_compliance_note: Mapped[bool] = mapped_column(Boolean, default=False)
    compliance_note: Mapped[str | None] = mapped_column(Text)
    freshness_hours: Mapped[int | None] = mapped_column(Integer)  # overrides platform default
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    attributes: Mapped[list["CategoryAttribute"]] = relationship(
        back_populates="category", order_by="CategoryAttribute.sort_order", cascade="all, delete-orphan"
    )


class CategoryAttribute(Base):
    __tablename__ = "category_attributes"
    __table_args__ = (UniqueConstraint("category_id", "code"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), index=True)
    code: Mapped[str] = mapped_column(String(60))
    name_uz: Mapped[str] = mapped_column(String(120))
    name_ru: Mapped[str] = mapped_column(String(120))
    name_en: Mapped[str | None] = mapped_column(String(120))
    data_type: Mapped[str] = mapped_column(String(20))  # text|number|boolean|date|select|multiselect
    unit_id: Mapped[int | None] = mapped_column(ForeignKey("units.id"))
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    is_filterable: Mapped[bool] = mapped_column(Boolean, default=False)
    is_matching_key: Mapped[bool] = mapped_column(Boolean, default=False)  # used by product matching
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    category: Mapped[Category] = relationship(back_populates="attributes")
    options: Mapped[list["AttributeOption"]] = relationship(
        back_populates="attribute", cascade="all, delete-orphan", lazy="selectin", order_by="AttributeOption.sort_order"
    )


class AttributeOption(Base):
    __tablename__ = "attribute_options"
    id: Mapped[int] = mapped_column(primary_key=True)
    attribute_id: Mapped[int] = mapped_column(ForeignKey("category_attributes.id", ondelete="CASCADE"), index=True)
    value: Mapped[str] = mapped_column(String(120))
    label_uz: Mapped[str] = mapped_column(String(120))
    label_ru: Mapped[str] = mapped_column(String(120))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    attribute: Mapped[CategoryAttribute] = relationship(back_populates="options")


class ExchangeRate(Base, TimestampMixin):
    """Recorded rates used for conversion to UZS. Entered by admins or an authorised feed."""

    __tablename__ = "exchange_rates"
    id: Mapped[int] = mapped_column(primary_key=True)
    currency: Mapped[str] = mapped_column(String(3), index=True)
    rate_to_uzs: Mapped[Decimal] = mapped_column(Rate)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    source: Mapped[str] = mapped_column(String(200))
