from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.contract import ContractResponse, JsonSchemaDocument
from app.schemas.enums import (
    CompatibilityDirection,
    CompatibilityMode,
    CompatibilityVerdict,
    VersionBumpType,
    VersionStatus,
)


class ContractVersionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    version: str = Field(min_length=1, max_length=64)
    schema_document: JsonSchemaDocument = Field(
        validation_alias=AliasChoices("schema", "schema_document"),
        serialization_alias="schema",
    )
    compatibility_mode: CompatibilityMode = CompatibilityMode.BACKWARD


class ContractVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    contract_id: UUID
    version: str
    status: VersionStatus
    schema_document: JsonSchemaDocument = Field(
        validation_alias=AliasChoices("schema_json", "schema_document"),
        serialization_alias="schema_json",
    )
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
    direction: CompatibilityDirection
    path: str | None = None


class DiffResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    added_properties: list[str] = Field(default_factory=list)
    removed_properties: list[str] = Field(default_factory=list)
    changed_properties: list[dict[str, Any]] = Field(default_factory=list)
    required_added: list[str] = Field(default_factory=list)
    required_removed: list[str] = Field(default_factory=list)
    additional_properties_changed: dict[str, Any] | None = None
    extensions_changed: dict[str, Any] | None = None


class CompatibilityCheckResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_id: UUID
    base_version: str
    candidate_version: str
    mode: CompatibilityMode
    verdict: CompatibilityVerdict
    version_bump: VersionBumpType | None = None
    backward_compatible: bool
    forward_compatible: bool
    full_compatible: bool
    policy_passed: bool | None = None
    violations: list[CompatibilityViolation] = Field(default_factory=list)
    diff: DiffResult


class PublishedContractResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: ContractResponse
    version: ContractVersionResponse
