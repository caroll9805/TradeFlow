from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8")[:72], bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8")[:72], hashed.encode())
    except ValueError:
        return False


def _encode(payload: dict[str, Any], expires: timedelta) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    body = {**payload, "iat": int(now.timestamp()), "exp": int((now + expires).timestamp())}
    return jwt.encode(body, s.jwt_secret, algorithm=s.jwt_algorithm)


def create_access_token(user_id: int, role: str) -> str:
    s = get_settings()
    return _encode({"sub": str(user_id), "role": role, "typ": "access"}, timedelta(minutes=s.access_token_minutes))


def create_refresh_token(user_id: int, token_version: int) -> str:
    s = get_settings()
    return _encode({"sub": str(user_id), "ver": token_version, "typ": "refresh"}, timedelta(days=s.refresh_token_days))


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    s = get_settings()
    data = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm])
    if data.get("typ") != expected_type:
        raise jwt.InvalidTokenError("wrong token type")
    return data
