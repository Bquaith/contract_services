from __future__ import annotations

from uuid import UUID as UUIDType, uuid4

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.schemas.enums import (
    CompatibilityMode,
    CompatibilityVerdict,
    ContractStatus,
    EntityType,
    TargetLayer,
    ValidationTarget,
    ValidationVerdict,
    VersionBumpType,
    VersionStatus,
)


class Contract(Base):
    __tablename__ = "contracts"
    __table_args__ = (UniqueConstraint("namespace", "name", name="uq_contract_namespace_name"),)

    id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    namespace: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    entity_type: Mapped[EntityType] = mapped_column(
        SAEnum(EntityType, name="entity_type", native_enum=False), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owners: Mapped[list[str]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    tags: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, server_default=text("'{}'"))
    target_layer: Mapped[TargetLayer] = mapped_column(
        SAEnum(TargetLayer, name="target_layer", native_enum=False), nullable=False
    )
    status: Mapped[ContractStatus] = mapped_column(
        SAEnum(ContractStatus, name="contract_status", native_enum=False),
        nullable=False,
        server_default=ContractStatus.DRAFT.value,
    )
    active_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    versions: Mapped[list[ContractVersion]] = relationship(back_populates="contract")
    compatibility_checks: Mapped[list[CompatibilityCheck]] = relationship(back_populates="contract")


class ContractVersion(Base):
    __tablename__ = "contract_versions"
    __table_args__ = (UniqueConstraint("contract_id", "version", name="uq_contract_version"),)

    id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    contract_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[VersionStatus] = mapped_column(
        SAEnum(VersionStatus, name="version_status", native_enum=False),
        nullable=False,
        server_default=VersionStatus.DRAFT.value,
    )
    schema_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    compatibility_mode: Mapped[CompatibilityMode] = mapped_column(
        SAEnum(CompatibilityMode, name="compatibility_mode", native_enum=False),
        nullable=False,
        server_default=CompatibilityMode.BACKWARD.value,
    )
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("'system'")
    )
    is_locked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )

    contract: Mapped[Contract] = relationship(back_populates="versions")


class CompatibilityCheck(Base):
    __tablename__ = "compatibility_checks"

    id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    contract_id: Mapped[UUIDType] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contracts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    base_version: Mapped[str] = mapped_column(String(64), nullable=False)
    candidate_version: Mapped[str] = mapped_column(String(64), nullable=False)
    mode: Mapped[CompatibilityMode] = mapped_column(
        SAEnum(CompatibilityMode, name="compatibility_mode_check", native_enum=False), nullable=False
    )
    verdict: Mapped[CompatibilityVerdict] = mapped_column(
        SAEnum(CompatibilityVerdict, name="compatibility_verdict", native_enum=False), nullable=False
    )
    version_bump: Mapped[VersionBumpType | None] = mapped_column(
        SAEnum(VersionBumpType, name="version_bump_type", native_enum=False),
        nullable=True,
    )
    backward_compatible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    forward_compatible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    full_compatible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"), default=False
    )
    policy_passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    violations_json: Mapped[list[dict]] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'::jsonb")
    )
    diff_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[str] = mapped_column(
        String(255), nullable=False, server_default=text("'system'")
    )

    contract: Mapped[Contract] = relationship(back_populates="compatibility_checks")


class ValidationRun(Base):
    __tablename__ = "validation_runs"

    id: Mapped[UUIDType] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    target: Mapped[ValidationTarget] = mapped_column(
        SAEnum(ValidationTarget, name="validation_target", native_enum=False), nullable=False
    )
    input_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    verdict: Mapped[ValidationVerdict] = mapped_column(
        SAEnum(ValidationVerdict, name="validation_verdict", native_enum=False), nullable=False
    )
    details_json: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
