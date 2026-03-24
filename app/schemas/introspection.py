from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.contract import ContractResponse
from app.schemas.enums import EntityType, TargetLayer
from app.schemas.version import ContractVersionResponse


class IntrospectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    connection_string: str = Field(min_length=1)
    source_schema: str = Field(
        min_length=1,
        max_length=63,
        validation_alias="schema",
        serialization_alias="schema",
    )
    table_name: str = Field(min_length=1, max_length=63)
    namespace: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=120)
    entity_type: EntityType = EntityType.TABLE
    target_layer: TargetLayer

    @field_validator("entity_type")
    @classmethod
    def ensure_table_entity(cls, value: EntityType) -> EntityType:
        if value != EntityType.TABLE:
            raise ValueError("Only entity_type='table' is supported for introspection")
        return value


class IntrospectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract: ContractResponse
    version: ContractVersionResponse
