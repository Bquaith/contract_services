from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.contract import ContractSchema
from app.schemas.enums import ValidationVerdict


class ValidationViolation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    field: str | None = None


class SchemaValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema: ContractSchema


class SchemaValidationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    verdict: ValidationVerdict
    violations: list[ValidationViolation] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
