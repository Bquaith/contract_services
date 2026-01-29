from typing import Any

from app.schemas.contract import ContractSchema
from app.schemas.enums import CompatibilityMode, CompatibilityVerdict


def _classify_type_change(previous: str, current: str) -> CompatibilityVerdict:
    if previous == current:
        return CompatibilityVerdict.OK
    if previous == "int" and current == "float":
        return CompatibilityVerdict.WARN
    return CompatibilityVerdict.FAIL


def _append_violation(
    violations: list[dict[str, Any]],
    code: str,
    message: str,
    severity: CompatibilityVerdict,
    field: str | None = None,
) -> None:
    violations.append(
        {
            "code": code,
            "message": message,
            "severity": severity.value,
            "field": field,
        }
    )


def _final_verdict(violations: list[dict[str, Any]]) -> CompatibilityVerdict:
    severities = {entry["severity"] for entry in violations}
    if CompatibilityVerdict.FAIL.value in severities:
        return CompatibilityVerdict.FAIL
    if CompatibilityVerdict.WARN.value in severities:
        return CompatibilityVerdict.WARN
    return CompatibilityVerdict.OK


def evaluate_compatibility(
    base_schema: ContractSchema,
    candidate_schema: ContractSchema,
    mode: CompatibilityMode,
) -> tuple[CompatibilityVerdict, list[dict[str, Any]]]:
    if mode == CompatibilityMode.NONE:
        return (
            CompatibilityVerdict.WARN,
            [
                {
                    "code": "compatibility.mode.none",
                    "message": "Compatibility mode 'none' does not enforce rules",
                    "severity": CompatibilityVerdict.WARN.value,
                    "field": None,
                }
            ],
        )

    violations: list[dict[str, Any]] = []

    base_fields = {field.name: field for field in base_schema.fields}
    candidate_fields = {field.name: field for field in candidate_schema.fields}

    added = sorted(set(candidate_fields) - set(base_fields))
    removed = sorted(set(base_fields) - set(candidate_fields))
    common = sorted(set(base_fields) & set(candidate_fields))

    if mode in {CompatibilityMode.BACKWARD, CompatibilityMode.FULL}:
        for name in removed:
            if not base_fields[name].nullable:
                _append_violation(
                    violations,
                    code="compatibility.backward.removed_required",
                    message=f"Required field '{name}' cannot be removed in backward mode",
                    severity=CompatibilityVerdict.FAIL,
                    field=name,
                )
            else:
                _append_violation(
                    violations,
                    code="compatibility.backward.removed_nullable",
                    message=f"Nullable field '{name}' was removed",
                    severity=CompatibilityVerdict.WARN,
                    field=name,
                )

        for name in added:
            if not candidate_fields[name].nullable:
                _append_violation(
                    violations,
                    code="compatibility.backward.added_required",
                    message=f"Required field '{name}' cannot be added in backward mode",
                    severity=CompatibilityVerdict.FAIL,
                    field=name,
                )

    if mode in {CompatibilityMode.FORWARD, CompatibilityMode.FULL}:
        for name in removed:
            _append_violation(
                violations,
                code="compatibility.forward.removed_field",
                message=f"Field '{name}' cannot be removed in forward mode",
                severity=CompatibilityVerdict.FAIL,
                field=name,
            )

        for name in added:
            if not candidate_fields[name].nullable:
                _append_violation(
                    violations,
                    code="compatibility.forward.added_required",
                    message=f"Required field '{name}' cannot be added in forward mode",
                    severity=CompatibilityVerdict.FAIL,
                    field=name,
                )
            else:
                _append_violation(
                    violations,
                    code="compatibility.forward.added_nullable",
                    message=f"Nullable field '{name}' was added",
                    severity=CompatibilityVerdict.WARN,
                    field=name,
                )

    for name in common:
        base_field = base_fields[name]
        candidate_field = candidate_fields[name]

        if base_field.nullable and not candidate_field.nullable:
            _append_violation(
                violations,
                code="compatibility.field.nullable_to_required",
                message=f"Field '{name}' changed nullable=true to nullable=false",
                severity=CompatibilityVerdict.FAIL,
                field=name,
            )

        type_verdict = _classify_type_change(base_field.type.value, candidate_field.type.value)
        if type_verdict != CompatibilityVerdict.OK:
            _append_violation(
                violations,
                code="compatibility.field.type_changed",
                message=(
                    f"Field '{name}' type changed "
                    f"{base_field.type.value}->{candidate_field.type.value}"
                ),
                severity=type_verdict,
                field=name,
            )

    if base_schema.keys.model_dump(mode="json") != candidate_schema.keys.model_dump(mode="json"):
        _append_violation(
            violations,
            code="compatibility.keys.changed",
            message="Key definitions changed",
            severity=CompatibilityVerdict.WARN,
        )

    if base_schema.constraints != candidate_schema.constraints:
        _append_violation(
            violations,
            code="compatibility.constraints.changed",
            message="Constraints changed",
            severity=CompatibilityVerdict.WARN,
        )

    return _final_verdict(violations), violations
