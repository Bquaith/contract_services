from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.enums import ContractStatus, EntityType, TargetLayer

JsonSchemaDocument = dict[str, Any]


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
