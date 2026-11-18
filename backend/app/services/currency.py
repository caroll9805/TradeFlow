"""Currency conversion using recorded exchange rates (never silent, never hardcoded)."""
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ExchangeRate


class MissingExchangeRate(ValueError):
    pass


def to_uzs(db: Session, amount: Decimal, currency: str, at: datetime | None = None) -> tuple[Decimal, Decimal | None, datetime | None]:
    """Return (amount_uzs, rate_used, rate_as_of). UZS passes through with rate None."""
    currency = currency.upper()
    if currency == "UZS":
        return Decimal(amount).quantize(Decimal("0.01"), ROUND_HALF_UP), None, None
    q = select(ExchangeRate).where(ExchangeRate.currency == currency)
    if at is not None:
        q = q.where(ExchangeRate.as_of <= at)
    rate = db.scalar(q.order_by(ExchangeRate.as_of.desc()).limit(1))
    if rate is None and at is not None:  # fall back to earliest available after `at`
        rate = db.scalar(select(ExchangeRate).where(ExchangeRate.currency == currency).order_by(ExchangeRate.as_of.asc()).limit(1))
    if rate is None:
        raise MissingExchangeRate(f"No recorded exchange rate for {currency}; add one in Admin → Exchange rates")
    value = (Decimal(amount) * Decimal(rate.rate_to_uzs)).quantize(Decimal("0.01"), ROUND_HALF_UP)
    return value, Decimal(rate.rate_to_uzs), rate.as_of
