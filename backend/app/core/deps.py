"""Authentication & authorization dependencies. All checks are enforced server-side."""
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.models import Supplier, User

bearer = HTTPBearer(auto_error=False)


def _user_from_token(db: Session, creds: HTTPAuthorizationCredentials | None) -> User | None:
    if creds is None:
        return None
    try:
        data = decode_token(creds.credentials, "access")
    except jwt.PyJWTError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Inactive or unknown user")
    return user


def get_optional_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User | None:
    return _user_from_token(db, creds)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer), db: Session = Depends(get_db)
) -> User:
    user = _user_from_token(db, creds)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    return user


def require(*perms: str) -> Callable[..., User]:
    """Dependency: user must hold ALL listed permission codes."""

    def checker(user: User = Depends(get_current_user)) -> User:
        missing = [p for p in perms if p not in user.permission_codes]
        if missing:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return checker


def has(user: User | None, perm: str) -> bool:
    return bool(user) and perm in user.permission_codes


def can_manage_supplier(user: User, supplier: Supplier) -> bool:
    """Object-level check: admins with suppliers.manage_all, or members of the supplier's organization."""
    if has(user, "suppliers.manage_all"):
        return True
    return supplier.organization_id is not None and supplier.organization_id in user.organization_ids


def ensure_can_manage_supplier(user: User, supplier: Supplier) -> None:
    if not can_manage_supplier(user, supplier):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You cannot manage this supplier")
