from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.contract import ContractResponse, ContractSchema
from app.schemas.enums import CompatibilityMode, CompatibilityVerdict, VersionStatus


class ContractVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(min_length=1, max_length=64)
    schema: ContractSchema
    compatibility_mode: CompatibilityMode = CompatibilityMode.BACKWARD


class ContractVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    contract_id: UUID
    version: str
    status: VersionStatus
    schema_json: dict[str, Any]
    checksum: str
    compatibility_mode: CompatibilityMode
    created_at: datetime
    created_by: str
    is_locked: bool


class CompatibilityCheckRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    base_version: str | None = None
    mode: CompatibilityMode | None = None


class CompatibilityViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    severity: CompatibilityVerdict
    field: str | None = None


class DiffResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added_fields: list[str] = Field(default_factory=list)
    removed_fields: list[str] = Field(default_factory=list)
    changed_fields: list[dict[str, Any]] = Field(default_factory=list)
    changed_keys: dict[str, Any] | None = None
    changed_constraints: dict[str, Any] | None = None


class CompatibilityCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: UUID
    base_version: str
    candidate_version: str
    mode: CompatibilityMode
    verdict: CompatibilityVerdict
    violations: list[CompatibilityViolation] = Field(default_factory=list)
    diff: DiffResult


class PublishedContractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: ContractResponse
    version: ContractVersionResponse
