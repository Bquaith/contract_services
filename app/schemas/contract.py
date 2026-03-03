from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.enums import ContractStatus, EntityType, FieldType, TargetLayer


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128)
    type: FieldType
    nullable: bool = True
    default: Any | None = None
    description: str | None = None


class KeysSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary: list[str] = Field(default_factory=list)
    business: list[str] = Field(default_factory=list)
    partition: list[str] = Field(default_factory=list)
    hash_keys: list[str] = Field(default_factory=list)


class ContractSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fields: list[FieldSpec] = Field(default_factory=list)
    keys: KeysSpec
    constraints: list[dict[str, Any]] = Field(default_factory=list)
    description: str | None = None


class ContractMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    namespace: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    entity_name: str = Field(min_length=1, max_length=255)
    entity_type: EntityType
    description: str | None = None
    owners: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    target_layer: TargetLayer

    @field_validator("owners", "tags")
    @classmethod
    def normalize_str_list(cls, value: list[str]) -> list[str]:
        normalized = [item.strip() for item in value if item and item.strip()]
        return list(dict.fromkeys(normalized))


class ContractCreateRequest(ContractMetadata):
    pass


class ContractUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str | None = None
    owners: list[str] | None = None
    tags: list[str] | None = None
    status: ContractStatus | None = None
    target_layer: TargetLayer | None = None


class ContractListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    namespace: str
    name: str
    entity_name: str
    entity_type: EntityType
    description: str | None
    owners: list[str]
    tags: list[str]
    target_layer: TargetLayer
    status: ContractStatus
    active_version: str | None
    created_at: datetime
    updated_at: datetime


class ContractResponse(ContractListItem):
    deleted_at: datetime | None = None
