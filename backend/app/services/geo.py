import math
from datetime import datetime, timezone
from decimal import Decimal

from app.models import Region


def aware(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; treat them as UTC."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def region_distance_km(a: Region | None, b: Region | None) -> float | None:
    """Distance between region administrative centres (approximate, region-level only)."""
    if not a or not b or a.center_lat is None or b.center_lat is None:
        return None
    if a.id == b.id:
        return 0.0
    return haversine_km(float(a.center_lat), float(a.center_lng), float(b.center_lat), float(b.center_lng))


def dec(v) -> Decimal | None:
    return None if v is None else Decimal(v)
