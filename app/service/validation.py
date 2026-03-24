from sqlalchemy.orm import Session

from app.db.models import ValidationRun
from app.schemas.enums import ValidationTarget
from app.schemas.validation import SchemaValidationResponse
from app.service.utils import calculate_checksum
from app.validators import validate_contract_schema


class ValidationService:
    def __init__(self, session: Session):
        self.session = session

    def validate_schema(self, schema_payload: dict) -> SchemaValidationResponse:
        result = validate_contract_schema(schema_payload)
        checksum = calculate_checksum(schema_payload)

        run = ValidationRun(
            target=ValidationTarget.SCHEMA,
            input_ref=checksum,
            verdict=result.verdict,
            details_json={
                "violations": [item.model_dump(mode="json") for item in result.violations],
                "details": result.details,
            },
        )

        self.session.add(run)
        self.session.commit()

        return result
