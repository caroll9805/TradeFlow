from typing import Any

from sqlalchemy.orm import Session

from app.models import AuditLog, User


def audit(db: Session, user: User | None, action: str, entity_type: str, entity_id: Any = None,
          changes: dict | None = None, ip: str | None = None) -> None:
    db.add(AuditLog(
        user_id=user.id if user else None,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        changes=_jsonable(changes) if changes else None,
        ip_address=ip,
    ))


def _jsonable(v: Any) -> Any:
    from datetime import date, datetime
    from decimal import Decimal

    if isinstance(v, dict):
        return {k: _jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [_jsonable(x) for x in v]
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v
