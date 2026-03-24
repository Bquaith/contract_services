from __future__ import annotations

from typing import Any
from typing import cast

from jsonschema.validators import validator_for  # type: ignore[import-untyped]

from app.schemas.contract import JsonSchemaDocument
from app.schemas.enums import (
    CompatibilityDirection,
    CompatibilityMode,
    CompatibilityVerdict,
    VersionBumpType,
)


def _append_violation(
    violations: list[dict[str, Any]],
    *,
    code: str,
    message: str,
    direction: CompatibilityDirection,
    path: str | None = None,
    severity: CompatibilityVerdict = CompatibilityVerdict.FAIL,
) -> None:
    violations.append(
        {
            "code": code,
            "message": message,
            "severity": severity.value,
            "direction": direction.value,
            "path": path,
        }
    )


def _type_label(schema: JsonSchemaDocument) -> str:
    if "const" in schema:
        return "const"
    if "enum" in schema:
        return "enum"
    return str(schema.get("type", "any"))


def _path(base_path: str, fragment: str) -> str:
    return f"{base_path}.{fragment}" if base_path else fragment


def _is_any_schema(schema: JsonSchemaDocument) -> bool:
    return set(schema).issubset({"title", "description", "default"})


def _target_accepts_value(target: JsonSchemaDocument, value: Any) -> bool:
    validator_cls = validator_for(target)
    validator = validator_cls(target)
    return cast(bool, validator.is_valid(value))


def _same_or_wider_type(source_type: str, target_type: str) -> bool:
    return source_type == target_type or (source_type == "integer" and target_type == "number")


def _lower_bound(schema: JsonSchemaDocument) -> tuple[float | int, bool] | None:
    if "exclusiveMinimum" in schema:
        return (schema["exclusiveMinimum"], True)
    if "minimum" in schema:
        return (schema["minimum"], False)
    return None


def _upper_bound(schema: JsonSchemaDocument) -> tuple[float | int, bool] | None:
    if "exclusiveMaximum" in schema:
        return (schema["exclusiveMaximum"], True)
    if "maximum" in schema:
        return (schema["maximum"], False)
    return None


def _lower_bound_is_stricter_or_equal(
    source_bound: tuple[float | int, bool] | None,
    target_bound: tuple[float | int, bool] | None,
) -> bool:
    if target_bound is None:
        return True
    if source_bound is None:
        return False

    source_value, source_exclusive = source_bound
    target_value, target_exclusive = target_bound
    if source_value > target_value:
        return True
    if source_value < target_value:
        return False
    if source_exclusive and not target_exclusive:
        return True
    return source_exclusive == target_exclusive


def _upper_bound_is_stricter_or_equal(
    source_bound: tuple[float | int, bool] | None,
    target_bound: tuple[float | int, bool] | None,
) -> bool:
    if target_bound is None:
        return True
    if source_bound is None:
        return False

    source_value, source_exclusive = source_bound
    target_value, target_exclusive = target_bound
    if source_value < target_value:
        return True
    if source_value > target_value:
        return False
    if source_exclusive and not target_exclusive:
        return True
    return source_exclusive == target_exclusive


def _compare_string_constraints(
    source: JsonSchemaDocument,
    target: JsonSchemaDocument,
    *,
    direction: CompatibilityDirection,
    path: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    target_min = target.get("minLength")
    source_min = source.get("minLength")
    if target_min is not None and (source_min is None or source_min < target_min):
        _append_violation(
            violations,
            code="compatibility.string.min_length",
            message="String minLength became stricter",
            direction=direction,
            path=path,
        )

    target_max = target.get("maxLength")
    source_max = source.get("maxLength")
    if target_max is not None and (source_max is None or source_max > target_max):
        _append_violation(
            violations,
            code="compatibility.string.max_length",
            message="String maxLength became stricter",
            direction=direction,
            path=path,
        )

    target_pattern = target.get("pattern")
    source_pattern = source.get("pattern")
    if target_pattern is not None and source_pattern != target_pattern:
        _append_violation(
            violations,
            code="compatibility.string.pattern",
            message="String pattern became stricter or changed",
            direction=direction,
            path=path,
        )

    target_format = target.get("format")
    source_format = source.get("format")
    if target_format is not None and source_format != target_format:
        _append_violation(
            violations,
            code="compatibility.string.format",
            message="String format became stricter or changed",
            direction=direction,
            path=path,
        )

    return violations


def _compare_numeric_constraints(
    source: JsonSchemaDocument,
    target: JsonSchemaDocument,
    *,
    direction: CompatibilityDirection,
    path: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    if not _lower_bound_is_stricter_or_equal(_lower_bound(source), _lower_bound(target)):
        _append_violation(
            violations,
            code="compatibility.number.minimum",
            message="Numeric lower bound became stricter",
            direction=direction,
            path=path,
        )

    if not _upper_bound_is_stricter_or_equal(_upper_bound(source), _upper_bound(target)):
        _append_violation(
            violations,
            code="compatibility.number.maximum",
            message="Numeric upper bound became stricter",
            direction=direction,
            path=path,
        )

    return violations


def _compare_array_constraints(
    source: JsonSchemaDocument,
    target: JsonSchemaDocument,
    *,
    direction: CompatibilityDirection,
    path: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    target_min_items = target.get("minItems")
    source_min_items = source.get("minItems")
    if target_min_items is not None and (source_min_items is None or source_min_items < target_min_items):
        _append_violation(
            violations,
            code="compatibility.array.min_items",
            message="Array minItems became stricter",
            direction=direction,
            path=path,
        )

    target_max_items = target.get("maxItems")
    source_max_items = source.get("maxItems")
    if target_max_items is not None and (source_max_items is None or source_max_items > target_max_items):
        _append_violation(
            violations,
            code="compatibility.array.max_items",
            message="Array maxItems became stricter",
            direction=direction,
            path=path,
        )

    source_items = source.get("items")
    target_items = target.get("items")
    if target_items is not None:
        if source_items is None:
            _append_violation(
                violations,
                code="compatibility.array.items",
                message="Array items became stricter",
                direction=direction,
                path=_path(path, "items"),
            )
        else:
            violations.extend(
                _check_subset(
                    source_items,
                    target_items,
                    direction=direction,
                    path=_path(path, "items"),
                )
            )

    return violations


def _compare_object_constraints(
    source: JsonSchemaDocument,
    target: JsonSchemaDocument,
    *,
    direction: CompatibilityDirection,
    path: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    source_properties = source.get("properties", {})
    target_properties = target.get("properties", {})
    source_required = set(source.get("required", []))
    target_required = set(target.get("required", []))

    for name in sorted(target_required - source_required):
        _append_violation(
            violations,
            code="compatibility.object.required",
            message=f"Property '{name}' became required",
            direction=direction,
            path=_path(path, name),
        )

    target_additional_properties = target.get("additionalProperties", True)
    source_additional_properties = source.get("additionalProperties", True)

    for name, property_schema in source_properties.items():
        property_path = _path(path, name)
        if name in target_properties:
            violations.extend(
                _check_subset(
                    property_schema,
                    target_properties[name],
                    direction=direction,
                    path=property_path,
                )
            )
        elif not target_additional_properties:
            _append_violation(
                violations,
                code="compatibility.object.property_removed",
                message=f"Property '{name}' is no longer accepted",
                direction=direction,
                path=property_path,
            )

    if source_additional_properties and not target_additional_properties:
        _append_violation(
            violations,
            code="compatibility.object.additional_properties",
            message="additionalProperties changed from true to false",
            direction=direction,
            path=path or "$",
        )

    return violations


def _check_subset(  # noqa: C901
    source: JsonSchemaDocument,
    target: JsonSchemaDocument,
    *,
    direction: CompatibilityDirection,
    path: str,
) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []

    if _is_any_schema(target):
        return violations
    if _is_any_schema(source):
        _append_violation(
            violations,
            code="compatibility.schema.any_to_restricted",
            message="An unconstrained schema cannot be narrowed without breaking compatibility",
            direction=direction,
            path=path or "$",
        )
        return violations

    if "const" in source:
        if not _target_accepts_value(target, source["const"]):
            _append_violation(
                violations,
                code="compatibility.schema.const",
                message="Constant value is not accepted by the target schema",
                direction=direction,
                path=path or "$",
            )
        return violations

    if "enum" in source:
        invalid_values = [value for value in source["enum"] if not _target_accepts_value(target, value)]
        if invalid_values:
            _append_violation(
                violations,
                code="compatibility.schema.enum",
                message="Enum values are not fully accepted by the target schema",
                direction=direction,
                path=path or "$",
            )
        return violations

    if "const" in target or "enum" in target:
        _append_violation(
            violations,
            code="compatibility.schema.finite_target",
            message="Target schema is finite but source schema is broader",
            direction=direction,
            path=path or "$",
        )
        return violations

    source_type = source.get("type")
    target_type = target.get("type")
    if target_type is not None:
        if source_type is None or not _same_or_wider_type(source_type, target_type):
            _append_violation(
                violations,
                code="compatibility.schema.type",
                message=(
                    f"Schema type changed from '{_type_label(source)}' "
                    f"to incompatible '{_type_label(target)}'"
                ),
                direction=direction,
                path=path or "$",
            )
            return violations

    effective_type = source_type or target_type
    if effective_type == "object":
        violations.extend(_compare_object_constraints(source, target, direction=direction, path=path))
    elif effective_type == "array":
        violations.extend(_compare_array_constraints(source, target, direction=direction, path=path))
    elif effective_type == "string":
        violations.extend(_compare_string_constraints(source, target, direction=direction, path=path))
    elif effective_type in {"integer", "number"}:
        violations.extend(_compare_numeric_constraints(source, target, direction=direction, path=path))

    return violations


def build_compatibility_report(
    base_schema: JsonSchemaDocument,
    candidate_schema: JsonSchemaDocument,
) -> dict[str, Any]:
    backward_violations = _check_subset(
        base_schema,
        candidate_schema,
        direction=CompatibilityDirection.BACKWARD,
        path="$",
    )
    forward_violations = _check_subset(
        candidate_schema,
        base_schema,
        direction=CompatibilityDirection.FORWARD,
        path="$",
    )
    violations = backward_violations + forward_violations

    backward_compatible = not backward_violations
    forward_compatible = not forward_violations
    full_compatible = backward_compatible and forward_compatible

    return {
        "backward_compatible": backward_compatible,
        "forward_compatible": forward_compatible,
        "full_compatible": full_compatible,
        "violations": violations,
    }


def verdict_for_mode(report: dict[str, Any], mode: CompatibilityMode) -> CompatibilityVerdict:
    if mode == CompatibilityMode.NONE:
        return CompatibilityVerdict.WARN
    if mode == CompatibilityMode.BACKWARD:
        return CompatibilityVerdict.OK if report["backward_compatible"] else CompatibilityVerdict.FAIL
    if mode == CompatibilityMode.FORWARD:
        return CompatibilityVerdict.OK if report["forward_compatible"] else CompatibilityVerdict.FAIL
    return CompatibilityVerdict.OK if report["full_compatible"] else CompatibilityVerdict.FAIL


def required_mode_for_bump(version_bump: VersionBumpType) -> CompatibilityMode:
    if version_bump == VersionBumpType.PATCH:
        return CompatibilityMode.FULL
    if version_bump == VersionBumpType.MINOR:
        return CompatibilityMode.BACKWARD
    return CompatibilityMode.NONE


def policy_passed_for_bump(report: dict[str, Any], version_bump: VersionBumpType) -> bool:
    if version_bump == VersionBumpType.PATCH:
        return bool(report["full_compatible"])
    if version_bump == VersionBumpType.MINOR:
        return bool(report["backward_compatible"])
    return True


def evaluate_compatibility(
    base_schema: JsonSchemaDocument,
    candidate_schema: JsonSchemaDocument,
    mode: CompatibilityMode,
) -> tuple[dict[str, Any], CompatibilityVerdict, list[dict[str, Any]]]:
    report = build_compatibility_report(base_schema, candidate_schema)
    verdict = verdict_for_mode(report, mode)
    return report, verdict, report["violations"]
