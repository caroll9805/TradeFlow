"""Request/response schemas. All user input is validated here."""
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, HttpUrl, field_validator

Lang = Literal["uz", "ru", "en"]
PriceType = Literal["wholesale", "retail", "negotiated", "other"]
SupplierType = Literal["manufacturer", "wholesaler", "distributor", "importer", "retail", "other"]
AttrType = Literal["text", "number", "boolean", "date", "select", "multiselect"]
Currency = Field(default="UZS", pattern=r"^[A-Z]{3}$")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- auth
class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    account_type: Literal["buyer", "supplier", "manufacturer"]
    organization_name: str = Field(min_length=2, max_length=255)
    region_id: int | None = None
    tin: str | None = Field(default=None, pattern=r"^\d{9,14}$")
    supplier_type: SupplierType | None = None
    locale: Lang = "uz"

    @field_validator("password")
    @classmethod
    def strong(cls, v: str) -> str:
        if not any(c.isdigit() for c in v) or not any(c.isalpha() for c in v):
            raise ValueError("Password must contain letters and digits")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshIn(BaseModel):
    refresh_token: str


class TokenOut(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=40)
    locale: Lang | None = None


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(min_length=8, max_length=128)


# ---------------- reference
class RegionIn(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    name_uz: str
    name_ru: str
    name_en: str
    aliases: list[str] = []
    center_lat: Decimal | None = Field(default=None, ge=37, le=46)
    center_lng: Decimal | None = Field(default=None, ge=55, le=74)
    sort_order: int = 0


class DistrictIn(BaseModel):
    region_id: int
    name_uz: str = Field(min_length=1, max_length=120)
    name_ru: str = Field(min_length=1, max_length=120)


class UnitIn(BaseModel):
    code: str = Field(min_length=1, max_length=20, pattern=r"^[a-z0-9_]+$")
    name_uz: str
    name_ru: str
    name_en: str
    symbol: str
    dimension: Literal["mass", "volume", "length", "area", "count", "package"]
    factor_to_base: Decimal | None = Field(default=None, gt=0)
    aliases: list[str] = []


class UnitConversionIn(BaseModel):
    product_id: int | None = None
    from_unit_id: int
    to_unit_id: int
    factor: Decimal = Field(gt=0)


class AttributeOptionIn(BaseModel):
    value: str = Field(min_length=1, max_length=120)
    label_uz: str
    label_ru: str
    sort_order: int = 0


class CategoryAttributeIn(BaseModel):
    code: str = Field(min_length=1, max_length=60, pattern=r"^[a-z0-9_]+$")
    name_uz: str
    name_ru: str
    name_en: str | None = None
    data_type: AttrType
    unit_id: int | None = None
    is_required: bool = False
    is_filterable: bool = False
    is_matching_key: bool = False
    sort_order: int = 0
    options: list[AttributeOptionIn] = []


class CategoryIn(BaseModel):
    slug: str = Field(min_length=2, max_length=80, pattern=r"^[a-z0-9-]+$")
    name_uz: str = Field(min_length=1, max_length=150)
    name_ru: str = Field(min_length=1, max_length=150)
    name_en: str | None = None
    parent_id: int | None = None
    description: str | None = None
    icon: str | None = None
    keywords: list[str] = []
    is_active: bool = True
    requires_compliance_note: bool = False
    compliance_note: str | None = None
    freshness_hours: int | None = Field(default=None, gt=0)
    sort_order: int = 0


class ExchangeRateIn(BaseModel):
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    rate_to_uzs: Decimal = Field(gt=0)
    as_of: datetime
    source: str = Field(min_length=2, max_length=200)


# ---------------- catalog
class AttributeValueIn(BaseModel):
    attribute_id: int
    value: Any


class ProductIn(BaseModel):
    name: str = Field(min_length=2, max_length=300)
    description: str | None = Field(default=None, max_length=5000)
    category_id: int
    brand: str | None = Field(default=None, max_length=150)
    model: str | None = Field(default=None, max_length=150)
    manufacturer_id: int | None = None
    sku: str | None = Field(default=None, max_length=100)
    barcode: str | None = Field(default=None, pattern=r"^\d{6,14}$")
    base_unit_id: int
    country_of_origin: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    origin_type: Literal["domestic", "import", "unknown"] = "unknown"
    status: Literal["active", "draft", "archived", "pending_review"] = "active"
    search_terms: list[str] = []
    attributes: list[AttributeValueIn] = []
    image_urls: list[HttpUrl] = []


class ManufacturerIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    country_code: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    website: HttpUrl | None = None


class SupplierLocationIn(BaseModel):
    kind: Literal["warehouse", "office", "store", "plant"] = "warehouse"
    name: str | None = None
    region_id: int
    district_id: int | None = None
    address: str | None = None
    lat: Decimal | None = Field(default=None, ge=37, le=46)
    lng: Decimal | None = Field(default=None, ge=55, le=74)


class SupplierIn(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    legal_name: str | None = None
    tin: str | None = Field(default=None, pattern=r"^\d{9,14}$")
    supplier_type: SupplierType
    description: str | None = Field(default=None, max_length=5000)
    phone: str | None = Field(default=None, max_length=40)
    email: EmailStr | None = None
    website: HttpUrl | None = None
    social_links: dict[str, HttpUrl] = {}
    region_id: int
    district_id: int | None = None
    address: str | None = None
    category_ids: list[int] = []
    locations: list[SupplierLocationIn] = []


class OfferIn(BaseModel):
    supplier_id: int
    product_id: int
    price: Decimal = Field(gt=0, max_digits=20, decimal_places=2)
    currency: str = Currency
    unit_id: int
    moq: Decimal | None = Field(default=None, ge=0)
    available_qty: Decimal | None = Field(default=None, ge=0)
    region_id: int
    district_id: int | None = None
    location_id: int | None = None
    delivery_available: bool = False
    delivery_cost_uzs: Decimal | None = Field(default=None, ge=0)
    delivery_regions: list[int] = []
    other_fees_uzs: Decimal | None = Field(default=None, ge=0)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    price_type: PriceType = "wholesale"
    source_url: HttpUrl | None = None


class OfferUpdate(BaseModel):
    price: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    unit_id: int | None = None
    moq: Decimal | None = Field(default=None, ge=0)
    available_qty: Decimal | None = Field(default=None, ge=0)
    delivery_available: bool | None = None
    delivery_cost_uzs: Decimal | None = Field(default=None, ge=0)
    delivery_regions: list[int] | None = None
    other_fees_uzs: Decimal | None = Field(default=None, ge=0)
    valid_until: datetime | None = None
    is_active: bool | None = None


class ObservationIn(BaseModel):
    product_id: int
    price: Decimal = Field(gt=0)
    currency: str = Currency
    unit_id: int
    region_id: int
    price_type: PriceType = "retail"
    data_source_id: int
    supplier_id: int | None = None
    observed_at: datetime
    source_url: HttpUrl | None = None
    original_product_name: str | None = None


# ---------------- market data
class DataSourceIn(BaseModel):
    code: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9_-]+$")
    name: str = Field(min_length=2, max_length=200)
    source_type: Literal["supplier_submission", "marketplace", "official_statistics", "supplier_website",
                         "file_import", "manual", "api", "simulated"]
    default_provenance: Literal["supplier_declared", "marketplace_listed", "official_statistic",
                                "verified_transaction", "estimated", "simulated"]
    base_url: HttpUrl | None = None
    terms_status: Literal["unknown", "pending_review", "permitted", "not_permitted"] = "unknown"
    has_public_api: bool | None = None
    requires_auth: bool | None = None
    redistribution_allowed: bool | None = None
    price_kind: str | None = None
    review_notes: str | None = None
    reliability_score: Decimal = Field(default=Decimal("0.5"), ge=0, le=1)
    freshness_hours: int = Field(default=72, gt=0)
    is_active: bool = True


class DataConnectorIn(BaseModel):
    data_source_id: int
    name: str = Field(min_length=2, max_length=200)
    connector_type: str
    config: dict[str, Any] = {}
    interval_minutes: int | None = Field(default=None, ge=15)
    is_enabled: bool = False


class MatchDecision(BaseModel):
    action: Literal["accept", "reject", "assign"]
    product_id: int | None = None


class VerificationDecision(BaseModel):
    status: Literal["verified", "rejected", "pending", "unverified"]
    notes: str | None = None


class SettingIn(BaseModel):
    value: Any
    description: str | None = None


# ---------------- procurement
class QuoteRequestIn(BaseModel):
    product_id: int
    supplier_id: int
    quantity: Decimal = Field(gt=0)
    unit_id: int
    delivery_region_id: int | None = None
    message: str | None = Field(default=None, max_length=2000)


class QuoteResponseIn(BaseModel):
    price: Decimal = Field(gt=0)
    currency: str = Currency
    unit_id: int
    valid_until: datetime | None = None
    message: str | None = Field(default=None, max_length=2000)


class RatingIn(BaseModel):
    score: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=2000)


class AssistantIn(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    include_simulated: bool = True
    language: Lang | None = None


class UserAdminUpdate(BaseModel):
    role_code: str | None = None
    is_active: bool | None = None


class RolePermissionsIn(BaseModel):
    permission_codes: list[str]
