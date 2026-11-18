from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import DateTime, Numeric
from sqlalchemy.orm import Mapped, mapped_column

# Monetary values: 18 integer digits + 2 decimals is ample for UZS.
Money = Numeric(20, 2)
# Normalized per-base-unit prices can be fractional (e.g. price per gram).
UnitPrice = Numeric(24, 6)
Quantity = Numeric(20, 4)
Rate = Numeric(20, 6)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )


__all__ = ["Money", "UnitPrice", "Quantity", "Rate", "utcnow", "TimestampMixin", "Decimal"]
