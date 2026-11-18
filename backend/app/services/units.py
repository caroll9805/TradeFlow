"""Unit normalization. Never compares incompatible units."""
from decimal import Decimal

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import Unit, UnitConversion


class UnitConversionError(ValueError):
    pass


def resolve_unit(db: Session, text: str | None) -> Unit | None:
    """Find a unit by code, symbol or alias (case-insensitive)."""
    if not text:
        return None
    t = text.strip().lower().rstrip(".")
    for u in db.scalars(select(Unit)).all():
        names = {u.code.lower(), u.symbol.lower(), u.name_uz.lower(), u.name_ru.lower(), u.name_en.lower()}
        names |= {a.lower() for a in (u.aliases or [])}
        if t in names:
            return u
    return None


def conversion_factor(db: Session, from_unit: Unit, to_unit: Unit, product_id: int | None = None) -> Decimal:
    """Return how many `to_unit` are in one `from_unit`.

    1. Same unit -> 1
    2. Product-specific conversion (either direction), possibly chained through the dimension base.
    3. Same physical dimension with known factors -> ratio of factors.
    Otherwise raises UnitConversionError."""
    if from_unit.id == to_unit.id:
        return Decimal(1)

    if product_id is not None:
        direct = _product_conv(db, product_id, from_unit.id, to_unit.id)
        if direct is not None:
            return direct
        # chain: from -> X (product conv) -> to (dimension conv)
        convs = db.scalars(
            select(UnitConversion).where(
                UnitConversion.product_id == product_id,
                or_(UnitConversion.from_unit_id == from_unit.id, UnitConversion.to_unit_id == from_unit.id),
            )
        ).all()
        for c in convs:
            if c.from_unit_id == from_unit.id:
                mid = db.get(Unit, c.to_unit_id)
                f1 = Decimal(c.factor)
            else:
                mid = db.get(Unit, c.from_unit_id)
                f1 = Decimal(1) / Decimal(c.factor)
            try:
                return f1 * _dimension_factor(mid, to_unit)
            except UnitConversionError:
                continue
        # chain the other way: from -> (dimension) -> X -> to (product conv)
        convs = db.scalars(
            select(UnitConversion).where(
                UnitConversion.product_id == product_id,
                or_(UnitConversion.from_unit_id == to_unit.id, UnitConversion.to_unit_id == to_unit.id),
            )
        ).all()
        for c in convs:
            if c.to_unit_id == to_unit.id:
                mid = db.get(Unit, c.from_unit_id)
                f2 = Decimal(c.factor)
            else:
                mid = db.get(Unit, c.to_unit_id)
                f2 = Decimal(1) / Decimal(c.factor)
            try:
                return _dimension_factor(from_unit, mid) * f2
            except UnitConversionError:
                continue

    return _dimension_factor(from_unit, to_unit)


def _product_conv(db: Session, product_id: int, a: int, b: int) -> Decimal | None:
    c = db.scalar(select(UnitConversion).where(UnitConversion.product_id == product_id,
                                               UnitConversion.from_unit_id == a, UnitConversion.to_unit_id == b))
    if c:
        return Decimal(c.factor)
    c = db.scalar(select(UnitConversion).where(UnitConversion.product_id == product_id,
                                               UnitConversion.from_unit_id == b, UnitConversion.to_unit_id == a))
    if c:
        return Decimal(1) / Decimal(c.factor)
    return None


def _dimension_factor(a: Unit, b: Unit) -> Decimal:
    if a.id == b.id:
        return Decimal(1)
    if a.dimension != b.dimension or a.factor_to_base is None or b.factor_to_base is None:
        raise UnitConversionError(f"Cannot convert {a.code} to {b.code}: incompatible units")
    return Decimal(a.factor_to_base) / Decimal(b.factor_to_base)


def try_conversion_factor(db: Session, from_unit: Unit, to_unit: Unit, product_id: int | None = None) -> Decimal | None:
    try:
        return conversion_factor(db, from_unit, to_unit, product_id)
    except UnitConversionError:
        return None
