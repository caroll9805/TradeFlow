"""Users, roles, permissions, organizations."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, ForeignKey, Integer, String, Table, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column("role_id", ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    Column("permission_id", ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(255))


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name_uz: Mapped[str] = mapped_column(String(100))
    name_ru: Mapped[str] = mapped_column(String(100))
    name_en: Mapped[str | None] = mapped_column(String(100))
    is_self_registrable: Mapped[bool] = mapped_column(Boolean, default=False)
    permissions: Mapped[list[Permission]] = relationship(secondary=role_permissions, lazy="selectin")


class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(40))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    locale: Mapped[str] = mapped_column(String(5), default="uz")
    token_version: Mapped[int] = mapped_column(Integer, default=0)  # bump to revoke refresh tokens
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    role: Mapped[Role] = relationship(lazy="joined")
    memberships: Mapped[list["OrganizationMember"]] = relationship(back_populates="user", lazy="selectin")

    @property
    def permission_codes(self) -> set[str]:
        return {p.code for p in self.role.permissions} if self.role else set()

    @property
    def organization_ids(self) -> list[int]:
        return [m.organization_id for m in self.memberships]


class Organization(Base, TimestampMixin):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    org_type: Mapped[str] = mapped_column(String(30))  # buyer | supplier | manufacturer | platform
    tin: Mapped[str | None] = mapped_column(String(20))  # STIR/INN where the business provides it
    region_id: Mapped[int | None] = mapped_column(ForeignKey("regions.id"))
    address: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(255))
    subscription_plan_id: Mapped[int | None] = mapped_column(ForeignKey("subscription_plans.id"))
    is_simulated: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    members: Mapped[list["OrganizationMember"]] = relationship(back_populates="organization")


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    member_role: Mapped[str] = mapped_column(String(20), default="owner")  # owner | member

    organization: Mapped[Organization] = relationship(back_populates="members", lazy="joined")
    user: Mapped[User] = relationship(back_populates="memberships")


class SubscriptionPlan(Base, TimestampMixin):
    """Architecture-ready monetization; billing is not implemented in the MVP."""

    __tablename__ = "subscription_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(50), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    audience: Mapped[str] = mapped_column(String(30))  # buyer | supplier | enterprise
    features: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
