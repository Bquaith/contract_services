from app.schemas.contract import ContractSchema, FieldSpec, KeysSpec
from app.schemas.enums import FieldType, ValidationVerdict
from app.validators import validate_contract_schema


def _valid_schema() -> ContractSchema:
    return ContractSchema(
        fields=[
            FieldSpec(name="id", type=FieldType.STRING, nullable=False),
            FieldSpec(name="amount", type=FieldType.INT, nullable=True),
        ],
        keys=KeysSpec(primary=["id"], hash_keys=["id"], partition=[]),
        constraints=[],
    )


def test_validate_schema_ok() -> None:
    result = validate_contract_schema(_valid_schema())
    assert result.verdict == ValidationVerdict.OK
    assert result.violations == []


def test_validate_schema_duplicate_field_names_fail() -> None:
    schema = ContractSchema(
        fields=[
            FieldSpec(name="id", type=FieldType.STRING, nullable=False),
            FieldSpec(name="id", type=FieldType.INT, nullable=True),
        ],
        keys=KeysSpec(primary=["id"], hash_keys=[], partition=[]),
        constraints=[],
    )

    result = validate_contract_schema(schema)
    assert result.verdict == ValidationVerdict.FAIL
    assert any(v.code == "schema.fields.duplicate" for v in result.violations)


def test_validate_schema_primary_key_required() -> None:
    schema = ContractSchema(
        fields=[FieldSpec(name="id", type=FieldType.STRING, nullable=False)],
        keys=KeysSpec(primary=[], hash_keys=[], partition=[]),
        constraints=[],
    )

    result = validate_contract_schema(schema)
    assert result.verdict == ValidationVerdict.FAIL
    assert any(v.code == "schema.keys.primary.empty" for v in result.violations)


def test_validate_schema_hash_keys_must_exist() -> None:
    schema = ContractSchema(
        fields=[FieldSpec(name="id", type=FieldType.STRING, nullable=False)],
        keys=KeysSpec(primary=["id"], hash_keys=["missing"], partition=[]),
        constraints=[],
    )

    result = validate_contract_schema(schema)
    assert result.verdict == ValidationVerdict.FAIL
    assert any(v.code == "schema.keys.hash.unknown" for v in result.violations)
