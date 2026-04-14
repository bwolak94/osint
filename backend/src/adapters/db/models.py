"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.domain.entities.types import (
    InvestigationStatus,
    NodeType,
    RelationshipType,
    ScanStatus,
    SubscriptionTier,
    UserRole,
)


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(1024), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.ANALYST, nullable=False
    )
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, name="subscription_tier"), default=SubscriptionTier.FREE, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    investigations: Mapped[list["InvestigationModel"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<UserModel id={self.id} email={self.email}>"


class InvestigationModel(Base):
    __tablename__ = "investigations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[InvestigationStatus] = mapped_column(
        Enum(InvestigationStatus, name="investigation_status"),
        default=InvestigationStatus.DRAFT,
        nullable=False,
    )
    owner_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True
    )
    seed_inputs: Mapped[dict] = mapped_column(JSON, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    owner: Mapped["UserModel"] = relationship(back_populates="investigations")
    identities: Mapped[list["IdentityModel"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )
    scan_results: Mapped[list["ScanResultModel"]] = relationship(
        back_populates="investigation", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<InvestigationModel id={self.id} title={self.title!r}>"


class IdentityModel(Base):
    __tablename__ = "identities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id"), nullable=False, index=True
    )
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    emails: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    phones: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    usernames: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    urls: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    nip: Mapped[str | None] = mapped_column(String(10), nullable=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sources: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    investigation: Mapped["InvestigationModel"] = relationship(back_populates="identities")

    def __repr__(self) -> str:
        return f"<IdentityModel id={self.id} display_name={self.display_name!r}>"


class ScanResultModel(Base):
    __tablename__ = "scan_results"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id"), nullable=False, index=True
    )
    scanner_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_value: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status"), default=ScanStatus.PENDING, nullable=False
    )
    raw_data: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)
    extracted_identifiers: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    investigation: Mapped["InvestigationModel"] = relationship(back_populates="scan_results")

    def __repr__(self) -> str:
        return f"<ScanResultModel id={self.id} scanner={self.scanner_name}>"
