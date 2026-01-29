from app.schemas.contract import ContractSchema
from app.schemas.enums import ValidationVerdict
from app.schemas.validation import SchemaValidationResponse, ValidationViolation


def validate_contract_schema(schema: ContractSchema) -> SchemaValidationResponse:
    violations: list[ValidationViolation] = []
    field_names = [field.name for field in schema.fields]
    field_set = set(field_names)

    if not field_names:
        violations.append(
            ValidationViolation(code="schema.fields.empty", message="At least one field is required")
        )

    duplicates = sorted({name for name in field_names if field_names.count(name) > 1})
    for duplicate in duplicates:
        violations.append(
            ValidationViolation(
                code="schema.fields.duplicate",
                message=f"Field name '{duplicate}' is duplicated",
                field=duplicate,
            )
        )

    if not schema.keys.primary:
        violations.append(
            ValidationViolation(code="schema.keys.primary.empty", message="Primary keys cannot be empty")
        )

    for key_name in schema.keys.primary:
        if key_name not in field_set:
            violations.append(
                ValidationViolation(
                    code="schema.keys.primary.unknown",
                    message=f"Primary key '{key_name}' does not exist in fields",
                    field=key_name,
                )
            )

    for key_name in schema.keys.business:
        if key_name not in field_set:
            violations.append(
                ValidationViolation(
                    code="schema.keys.business.unknown",
                    message=f"Business key '{key_name}' does not exist in fields",
                    field=key_name,
                )
            )

    for key_name in schema.keys.hash_keys:
        if key_name not in field_set:
            violations.append(
                ValidationViolation(
                    code="schema.keys.hash.unknown",
                    message=f"Hash key '{key_name}' does not exist in fields",
                    field=key_name,
                )
            )

    for key_name in schema.keys.partition:
        if key_name not in field_set:
            violations.append(
                ValidationViolation(
                    code="schema.keys.partition.unknown",
                    message=f"Partition key '{key_name}' does not exist in fields",
                    field=key_name,
                )
            )

    verdict = ValidationVerdict.FAIL if violations else ValidationVerdict.OK
    details = {
        "field_count": len(schema.fields),
        "primary_keys": schema.keys.primary,
        "constraint_count": len(schema.constraints),
    }

    return SchemaValidationResponse(verdict=verdict, violations=violations, details=details)
