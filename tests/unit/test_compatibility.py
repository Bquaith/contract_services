from app.compatibility.rules import evaluate_compatibility
from app.schemas.enums import CompatibilityMode, CompatibilityVerdict


def _schema_v1() -> dict:
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


def test_backward_add_optional_property_ok() -> None:
    old = _schema_v1()
    new = {
        **_schema_v1(),
        "properties": {
            **_schema_v1()["properties"],
            "comment": {"type": "string"},
        },
    }

    report, verdict, violations = evaluate_compatibility(old, new, CompatibilityMode.BACKWARD)
    assert report["backward_compatible"] is True
    assert report["forward_compatible"] is False
    assert verdict == CompatibilityVerdict.OK
    assert any(v["direction"] == "forward" for v in violations)


def test_backward_add_required_property_fail() -> None:
    old = _schema_v1()
    new = {
        **_schema_v1(),
        "properties": {
            **_schema_v1()["properties"],
            "country": {"type": "string"},
        },
        "required": ["id", "country"],
    }

    report, verdict, violations = evaluate_compatibility(old, new, CompatibilityMode.BACKWARD)
    assert report["backward_compatible"] is False
    assert verdict == CompatibilityVerdict.FAIL
    assert any(v["code"] == "compatibility.object.required" for v in violations)


def test_backward_integer_to_number_is_allowed() -> None:
    old = _schema_v1()
    new = {
        **_schema_v1(),
        "properties": {
            "id": {"type": "string"},
            "amount": {"type": "number"},
        },
    }

    report, verdict, violations = evaluate_compatibility(old, new, CompatibilityMode.BACKWARD)
    assert report["backward_compatible"] is True
    assert report["forward_compatible"] is False
    assert verdict == CompatibilityVerdict.OK
    assert any(v["code"] == "compatibility.schema.type" for v in violations)


def test_full_remove_property_fail() -> None:
    old = _schema_v1()
    new = {
        **_schema_v1(),
        "properties": {
            "id": {"type": "string"},
        },
    }

    report, verdict, _ = evaluate_compatibility(old, new, CompatibilityMode.FULL)
    assert report["full_compatible"] is False
    assert verdict == CompatibilityVerdict.FAIL
