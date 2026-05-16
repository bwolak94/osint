"""SQLAlchemy ORM models."""

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from src.core.domain.entities.types import (
    InvestigationStatus,
    NodeType,
    RelationshipType,
    ScanStatus,
    SubscriptionTier,
    UserRole,
)
from src.utils.time import utcnow


class ACLPermission(str, PyEnum):
    """Permission levels for investigation ACL entries."""
    VIEW = "view"
    EDIT = "edit"
    ADMIN = "admin"


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


class UserModel(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), default=UserRole.ANALYST, nullable=False
    )
    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        Enum(SubscriptionTier, name="subscription_tier"), default=SubscriptionTier.FREE, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_email_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    tos_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=True
    )

    investigations: Mapped[list["InvestigationModel"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )
    refresh_tokens: Mapped[list["RefreshTokenModel"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index(
            "ix_users_active_email",
            "email",
            postgresql_where=text("is_active = true"),
        ),
    )

    def __repr__(self) -> str:
        return f"<UserModel id={self.id} email={self.email}>"


class RefreshTokenModel(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    is_revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user: Mapped["UserModel"] = relationship(back_populates="refresh_tokens")

    __table_args__ = (
        # Partial composite index on active tokens: speeds up revoke_all_for_user
        # which filters WHERE user_id = ? AND is_revoked = false.
        Index(
            "ix_refresh_tokens_user_active",
            "user_id",
            "is_revoked",
            postgresql_where=text("is_revoked = false"),
        ),
        # Partial index on non-expired tokens speeds up token validity lookups.
        Index(
            "ix_refresh_tokens_active_expires",
            "token_hash",
            "expires_at",
            postgresql_where=text("is_revoked = false"),
        ),
    )

    def __repr__(self) -> str:
        return f"<RefreshTokenModel id={self.id} user_id={self.user_id}>"


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
    seed_inputs: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    shared_with: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
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

    __table_args__ = (
        # GIN index enables efficient array-containment queries on tags
        # (e.g. WHERE tags @> ARRAY['malware']).
        Index("ix_investigations_tags_gin", "tags", postgresql_using="gin"),
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
    metadata_: Mapped[dict] = mapped_column("metadata", JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("confidence_score BETWEEN 0.0 AND 1.0", name="ck_identities_confidence_range"),
        Index("ix_identities_emails_gin", "emails", postgresql_using="gin"),
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
    raw_data: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    extracted_identifiers: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    # nullable=False + default: always has a value; onupdate keeps it current.
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False
    )

    investigation: Mapped["InvestigationModel"] = relationship(back_populates="scan_results")

    __table_args__ = (
        Index("ix_scan_results_inv_scanner", "investigation_id", "scanner_name"),
        Index("ix_scan_results_inv_status", "investigation_id", "status"),
        # Composite index for time-ordered result listing per investigation.
        Index("ix_scan_results_inv_created", "investigation_id", "created_at"),
        # Standalone scanner_name index for admin/cross-investigation queries.
        Index("ix_scan_results_scanner_name", "scanner_name"),
    )

    def __repr__(self) -> str:
        return f"<ScanResultModel id={self.id} scanner={self.scanner_name}>"


class InvestigationACLModel(Base):
    """Fine-grained access control for investigations (view / edit / admin)."""

    __tablename__ = "investigation_acl"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission: Mapped[ACLPermission] = mapped_column(
        Enum(ACLPermission, native_enum=False, length=16),
        nullable=False,
    )
    granted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        Index("ix_acl_inv_user", "investigation_id", "user_id", unique=True),
        CheckConstraint("permission IN ('view', 'edit', 'admin')", name="ck_acl_permission_values"),
    )

    def __repr__(self) -> str:
        return f"<InvestigationACLModel inv={self.investigation_id} user={self.user_id} perm={self.permission}>"


class InvestigationRiskScoreModel(Base):
    """Cached risk score for an investigation, recomputed after each scan batch."""

    __tablename__ = "investigation_risk_scores"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    score: Mapped[float] = mapped_column(Float, nullable=False)
    breach_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    exposed_services: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    avg_confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    factors: Mapped[dict] = mapped_column(JSONB, default=dict, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    __table_args__ = (
        CheckConstraint("score BETWEEN 0.0 AND 100.0", name="ck_risk_score_range"),
    )

    def __repr__(self) -> str:
        return f"<InvestigationRiskScoreModel inv={self.investigation_id} score={self.score}>"


class ScannerQuotaModel(Base):
    """Per-workspace API quota tracking for each external scanner."""

    __tablename__ = "scanner_quotas"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    scanner_name: Mapped[str] = mapped_column(String(100), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    requests_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requests_limit: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    last_request_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        Index("ix_scanner_quotas_ws_scanner", "workspace_id", "scanner_name"),
    )

    def __repr__(self) -> str:
        return f"<ScannerQuotaModel ws={self.workspace_id} scanner={self.scanner_name} used={self.requests_used}>"


class EvidenceModel(Base):
    """Persistent evidence store with tamper-evident chain of custody. (#11)

    Replaces the in-memory ``_evidence_store`` dict in evidence_locker.py for
    production use. Each row maps to one ``EvidenceItem``; chain-of-custody
    entries are stored as a JSONB array so they are append-only from the DB's
    perspective (individual entries are never updated after insert).
    """

    __tablename__ = "evidence_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    investigation_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    # chain_of_custody: append-only JSONB array of CustodyEntry dicts
    chain_of_custody: Mapped[list] = mapped_column(JSONB, default=list, nullable=False)
    hash_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    content_hash_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    sealed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_admissible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    __table_args__ = (
        Index("ix_evidence_items_created_by_inv", "created_by", "investigation_id"),
        CheckConstraint("type IN ('screenshot','document','url','note','artifact','log','pcap','network_capture','memory_dump')", name="ck_evidence_type"),
    )

    def __repr__(self) -> str:
        return f"<EvidenceModel id={self.id} type={self.type} sealed={self.sealed}>"
