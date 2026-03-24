from app.schemas.enums import ValidationVerdict
from app.validators import validate_contract_schema


def _valid_schema() -> dict:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "amount": {"type": "integer"},
        },
        "required": ["id"],
        "additionalProperties": False,
        "x-primaryKey": ["id"],
    }


def test_validate_schema_ok() -> None:
    result = validate_contract_schema(_valid_schema())
    assert result.verdict == ValidationVerdict.OK
    assert result.violations == []


def test_validate_schema_rejects_unsupported_keyword() -> None:
    schema = _valid_schema()
    schema["oneOf"] = [{"type": "object"}]

    result = validate_contract_schema(schema)
    assert result.verdict == ValidationVerdict.FAIL
    assert any(v.code == "schema.profile.keyword.unsupported" for v in result.violations)


def test_validate_schema_required_property_must_exist() -> None:
    schema = _valid_schema()
    schema["required"] = ["id", "missing"]

    result = validate_contract_schema(schema)
    assert result.verdict == ValidationVerdict.FAIL
    assert any(v.code == "schema.profile.required.unknown" for v in result.violations)


def test_validate_schema_extensions_must_reference_known_properties() -> None:
    schema = _valid_schema()
    schema["x-primaryKey"] = ["missing"]

    result = validate_contract_schema(schema)
    assert result.verdict == ValidationVerdict.FAIL
    assert any(v.code == "schema.profile.extension.unknown_field" for v in result.violations)
