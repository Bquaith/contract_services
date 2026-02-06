from app.compatibility.rules import evaluate_compatibility
from app.schemas.contract import ContractSchema, FieldSpec, KeysSpec
from app.schemas.enums import CompatibilityMode, CompatibilityVerdict, FieldType


def _schema_v1() -> ContractSchema:
    return ContractSchema(
        fields=[
            FieldSpec(name="id", type=FieldType.STRING, nullable=False),
            FieldSpec(name="amount", type=FieldType.INT, nullable=True),
        ],
        keys=KeysSpec(primary=["id"], hash_keys=["id"], partition=[]),
        constraints=[],
    )


def test_backward_add_nullable_ok() -> None:
    old = _schema_v1()
    new = ContractSchema(
        fields=[
            FieldSpec(name="id", type=FieldType.STRING, nullable=False),
            FieldSpec(name="amount", type=FieldType.INT, nullable=True),
            FieldSpec(name="comment", type=FieldType.STRING, nullable=True),
        ],
        keys=KeysSpec(primary=["id"], hash_keys=["id"], partition=[]),
        constraints=[],
    )

    verdict, violations = evaluate_compatibility(old, new, CompatibilityMode.BACKWARD)
    assert verdict == CompatibilityVerdict.OK
    assert violations == []


def test_backward_add_required_fail() -> None:
    old = _schema_v1()
    new = ContractSchema(
        fields=[
            FieldSpec(name="id", type=FieldType.STRING, nullable=False),
            FieldSpec(name="amount", type=FieldType.INT, nullable=True),
            FieldSpec(name="country", type=FieldType.STRING, nullable=False),
        ],
        keys=KeysSpec(primary=["id"], hash_keys=["id"], partition=[]),
        constraints=[],
    )

    verdict, violations = evaluate_compatibility(old, new, CompatibilityMode.BACKWARD)
    assert verdict == CompatibilityVerdict.FAIL
    assert any(v["code"] == "compatibility.backward.added_required" for v in violations)


def test_backward_int_to_float_warn() -> None:
    old = _schema_v1()
    new = ContractSchema(
        fields=[
            FieldSpec(name="id", type=FieldType.STRING, nullable=False),
            FieldSpec(name="amount", type=FieldType.FLOAT, nullable=True),
        ],
        keys=KeysSpec(primary=["id"], hash_keys=["id"], partition=[]),
        constraints=[],
    )

    verdict, violations = evaluate_compatibility(old, new, CompatibilityMode.BACKWARD)
    assert verdict == CompatibilityVerdict.WARN
    assert any(v["severity"] == CompatibilityVerdict.WARN.value for v in violations)


def test_full_remove_field_fail() -> None:
    old = _schema_v1()
    new = ContractSchema(
        fields=[FieldSpec(name="id", type=FieldType.STRING, nullable=False)],
        keys=KeysSpec(primary=["id"], hash_keys=["id"], partition=[]),
        constraints=[],
    )

    verdict, _ = evaluate_compatibility(old, new, CompatibilityMode.FULL)
    assert verdict == CompatibilityVerdict.FAIL
