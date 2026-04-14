"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.domain.entities.identity import IdentityType
from src.core.domain.entities.investigation import InvestigationStatus


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(1024), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    # Relationships
    investigations: Mapped[list["InvestigationModel"]] = relationship(back_populates="owner", cascade="all, delete-orphan")

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
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    owner: Mapped["UserModel"] = relationship(back_populates="investigations")
    identities: Mapped[list["IdentityModel"]] = relationship(back_populates="investigation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<InvestigationModel id={self.id} title={self.title!r}>"


class IdentityModel(Base):
    __tablename__ = "identities"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id"), nullable=False, index=True
    )
    label: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[IdentityType] = mapped_column(
        Enum(IdentityType, name="identity_type"),
        default=IdentityType.UNKNOWN,
        nullable=False,
    )
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, default=dict, nullable=False)

    # Relationships
    investigation: Mapped["InvestigationModel"] = relationship(back_populates="identities")

    def __repr__(self) -> str:
        return f"<IdentityModel id={self.id} label={self.label!r}>"
