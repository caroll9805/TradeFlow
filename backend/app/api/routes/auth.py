import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.common import user_out
from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.ratelimit import auth_rate_limit, client_ip
from app.core.security import create_access_token, create_refresh_token, decode_token, hash_password, verify_password
from app.models import Organization, OrganizationMember, Region, Role, Supplier, User
from app.models.base import utcnow
from app.schemas import LoginIn, PasswordChange, ProfileUpdate, RefreshIn, RegisterIn, TokenOut
from app.services.audit import audit

router = APIRouter(prefix="/auth", tags=["auth"])


def _tokens(user: User) -> TokenOut:
    return TokenOut(access_token=create_access_token(user.id, user.role.code),
                    refresh_token=create_refresh_token(user.id, user.token_version))


@router.post("/register", response_model=TokenOut, status_code=201, dependencies=[Depends(auth_rate_limit)])
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == body.email.lower())):
        raise HTTPException(409, "Email is already registered")
    role = db.scalar(select(Role).where(Role.code == body.account_type, Role.is_self_registrable.is_(True)))
    if role is None:
        raise HTTPException(400, "This account type cannot be self-registered")
    if body.region_id and not db.get(Region, body.region_id):
        raise HTTPException(422, "Unknown region")
    if body.account_type in ("supplier", "manufacturer") and not body.region_id:
        raise HTTPException(422, "region_id is required for suppliers and manufacturers")
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), full_name=body.full_name,
                phone=body.phone, role_id=role.id, locale=body.locale)
    org = Organization(name=body.organization_name, org_type=body.account_type, tin=body.tin, region_id=body.region_id,
                       phone=body.phone, email=body.email.lower())
    db.add_all([user, org])
    db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=user.id, member_role="owner"))
    if body.account_type in ("supplier", "manufacturer"):
        # Registered, NOT verified. Verification is a separate admin process.
        db.add(Supplier(organization_id=org.id, name=body.organization_name, tin=body.tin,
                        supplier_type=body.supplier_type or ("manufacturer" if body.account_type == "manufacturer" else "wholesaler"),
                        region_id=body.region_id, phone=body.phone, email=body.email.lower(),
                        verification_status="unverified"))
    audit(db, user, "register", "user", user.id, {"account_type": body.account_type}, client_ip(request))
    db.commit()
    db.refresh(user)
    return _tokens(user)


@router.post("/login", response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled")
    user.last_login_at = utcnow()
    audit(db, user, "login", "user", user.id, ip=client_ip(request))
    db.commit()
    return _tokens(user)


@router.post("/refresh", response_model=TokenOut, dependencies=[Depends(auth_rate_limit)])
def refresh(body: RefreshIn, db: Session = Depends(get_db)):
    try:
        data = decode_token(body.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(401, "Invalid refresh token")
    user = db.get(User, int(data["sub"]))
    if not user or not user.is_active or data.get("ver") != user.token_version:
        raise HTTPException(401, "Refresh token revoked")
    return _tokens(user)


@router.post("/logout", status_code=204)
def logout(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.token_version += 1  # revokes all refresh tokens
    db.commit()


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.patch("/me")
def update_me(body: ProfileUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return user_out(user)


@router.post("/me/password", status_code=204)
def change_password(body: PasswordChange, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(body.new_password)
    user.token_version += 1
    audit(db, user, "password_change", "user", user.id)
    db.commit()
