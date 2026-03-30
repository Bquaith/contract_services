from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_validation_service
from app.auth import require_contract_schema
from app.schemas.validation import SchemaValidationRequest, SchemaValidationResponse
from app.service import ValidationService

router = APIRouter(tags=["validation"])


@router.post("/validate/schema", response_model=SchemaValidationResponse)
def validate_schema(
    payload: SchemaValidationRequest,
    _: Annotated[object, Depends(require_contract_schema)],
    service: Annotated[ValidationService, Depends(get_validation_service)],
) -> SchemaValidationResponse:
    return service.validate_schema(payload.schema_document)
