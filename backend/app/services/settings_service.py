"""Read adjustable business rules from the platform_settings table.

Defaults below are *technical fallbacks* used only if a key is missing; the seed writes the
real values into the database where admins can change them in the UI."""
from typing import Any

from sqlalchemy.orm import Session

from app.models import PlatformSetting

FALLBACKS: dict[str, Any] = {
    "ranking.weights": {"price": 0.45, "reliability": 0.2, "freshness": 0.15, "stock": 0.1, "distance": 0.1},
    "ranking.max_distance_km": 1200,
    "freshness.default_hours": 72,
    "matching.auto_accept_threshold": 0.92,
    "matching.review_threshold": 0.6,
    "analytics.mover_threshold_pct": 5.0,
    "analytics.mover_window_days": 14,
    "analytics.anomaly_z_threshold": 3.5,
    "analytics.min_points_for_forecast": 8,
    "analytics.min_points_for_isolation_forest": 30,
    "data_quality.weights": {"has_supplier": 0.2, "has_source_url": 0.15, "unit_normalized": 0.25,
                              "region_known": 0.15, "match_confidence": 0.25},
}


def get_setting(db: Session, key: str) -> Any:
    row = db.get(PlatformSetting, key)
    if row is not None:
        return row.value
    return FALLBACKS.get(key)
