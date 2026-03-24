from __future__ import annotations

import json
from typing import Any

from jsonschema import SchemaError  # type: ignore[import-untyped]
from jsonschema.validators import validator_for  # type: ignore[import-untyped]

from app.schemas.contract import JsonSchemaDocument
from app.schemas.enums import ValidationVerdict
from app.schemas.validation import SchemaValidationResponse, ValidationViolation

SUPPORTED_SCHEMA_TYPES = {"object", "array", "string", "integer", "number", "boolean", "null"}
PROFILE_KEYS = {
    "$schema",
    "type",
    "title",
    "description",
    "default",
    "enum",
    "const",
    "format",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "exclusiveMaximum",
    "minLength",
    "maxLength",
    "pattern",
    "properties",
    "required",
    "additionalProperties",
    "items",
    "minItems",
    "maxItems",
}
ROOT_EXTENSION_KEYS = {
    "x-primaryKey",
    "x-businessKey",
}
STRING_KEYWORDS = {"format", "minLength", "maxLength", "pattern"}
NUMERIC_KEYWORDS = {"minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum"}
ARRAY_KEYWORDS = {"items", "minItems", "maxItems"}


def _path_to_string(path: tuple[str | int, ...]) -> str:
    if not path:
        return "$"

    chunks = ["$"]
    for part in path:
        if isinstance(part, int):
            chunks.append(f"[{part}]")
        else:
            chunks.append(f".{part}")
    return "".join(chunks)


def _append_violation(
    violations: list[ValidationViolation],
    code: str,
    message: str,
    path: tuple[str | int, ...] = (),
) -> None:
    violations.append(
        ValidationViolation(
            code=code,
            message=message,
            path=_path_to_string(path),
        )
    )


def _ensure_extension_list(
    schema: JsonSchemaDocument,
    extension_key: str,
    properties: dict[str, Any],
    violations: list[ValidationViolation],
) -> None:
    raw_value = schema.get(extension_key)
    if raw_value is None:
        return

    if not isinstance(raw_value, list) or any(not isinstance(item, str) or not item for item in raw_value):
        _append_violation(
            violations,
            code="schema.profile.extension.invalid",
            message=f"'{extension_key}' must be a list of non-empty strings",
            path=(extension_key,),
        )
        return

    if len(set(raw_value)) != len(raw_value):
        _append_violation(
            violations,
            code="schema.profile.extension.duplicate",
            message=f"'{extension_key}' contains duplicate field names",
            path=(extension_key,),
        )

    for field_name in raw_value:
        if field_name not in properties:
            _append_violation(
                violations,
                code="schema.profile.extension.unknown_field",
                message=f"'{extension_key}' references unknown property '{field_name}'",
                path=(extension_key,),
            )


def _validate_schema_profile(  # noqa: C901
    schema: Any,
    violations: list[ValidationViolation],
    path: tuple[str | int, ...] = (),
    *,
    is_root: bool = False,
) -> None:
    if not isinstance(schema, dict):
        _append_violation(
            violations,
            code="schema.profile.node.invalid",
            message="Schema nodes must be JSON objects",
            path=path,
        )
        return

    allowed_keys = PROFILE_KEYS | (ROOT_EXTENSION_KEYS if is_root else set())
    unknown_keys = sorted(set(schema) - allowed_keys)
    for unknown_key in unknown_keys:
        _append_violation(
            violations,
            code="schema.profile.keyword.unsupported",
            message=f"Keyword '{unknown_key}' is not supported by the contract profile",
            path=path + (unknown_key,),
        )

    schema_type = schema.get("type")
    if schema_type is not None and (not isinstance(schema_type, str) or schema_type not in SUPPORTED_SCHEMA_TYPES):
        _append_violation(
            violations,
            code="schema.profile.type.invalid",
            message="'type' must be one of the supported JSON Schema primitive types",
            path=path + ("type",),
        )

    if is_root and schema.get("type") != "object":
        _append_violation(
            violations,
            code="schema.profile.root.type",
            message="Contract schema root must have type='object'",
            path=path + ("type",),
        )

    properties: dict[str, Any] = {}
    raw_properties = schema.get("properties")
    if raw_properties is not None:
        if schema_type != "object":
            _append_violation(
                violations,
                code="schema.profile.properties.type_mismatch",
                message="'properties' is only supported for object schemas",
                path=path + ("properties",),
            )
        if not isinstance(raw_properties, dict):
            _append_violation(
                violations,
                code="schema.profile.properties.invalid",
                message="'properties' must be an object",
                path=path + ("properties",),
            )
        else:
            properties = raw_properties
            for property_name, property_schema in properties.items():
                if not isinstance(property_name, str) or not property_name:
                    _append_violation(
                        violations,
                        code="schema.profile.properties.name.invalid",
                        message="Property names must be non-empty strings",
                        path=path + ("properties",),
                    )
                    continue
                _validate_schema_profile(
                    property_schema,
                    violations,
                    path=path + ("properties", property_name),
                )

    if is_root and not properties:
        _append_violation(
            violations,
            code="schema.profile.properties.empty",
            message="Contract schema must define at least one property",
            path=path + ("properties",),
        )

    raw_required = schema.get("required")
    if raw_required is not None:
        if schema_type != "object":
            _append_violation(
                violations,
                code="schema.profile.required.type_mismatch",
                message="'required' is only supported for object schemas",
                path=path + ("required",),
            )
        elif not isinstance(raw_required, list) or any(
            not isinstance(item, str) or not item for item in raw_required
        ):
            _append_violation(
                violations,
                code="schema.profile.required.invalid",
                message="'required' must be a list of non-empty strings",
                path=path + ("required",),
            )
        else:
            if len(set(raw_required)) != len(raw_required):
                _append_violation(
                    violations,
                    code="schema.profile.required.duplicate",
                    message="'required' contains duplicate property names",
                    path=path + ("required",),
                )

            unknown_required = sorted(set(raw_required) - set(properties))
            for field_name in unknown_required:
                _append_violation(
                    violations,
                    code="schema.profile.required.unknown",
                    message=f"Required property '{field_name}' is not defined in properties",
                    path=path + ("required",),
                )

    if "additionalProperties" in schema:
        if schema_type != "object":
            _append_violation(
                violations,
                code="schema.profile.additional_properties.type_mismatch",
                message="'additionalProperties' is only supported for object schemas",
                path=path + ("additionalProperties",),
            )
        elif not isinstance(schema["additionalProperties"], bool):
            _append_violation(
                violations,
                code="schema.profile.additional_properties.invalid",
                message="'additionalProperties' must be a boolean",
                path=path + ("additionalProperties",),
            )

    if "items" in schema:
        if schema_type != "array":
            _append_violation(
                violations,
                code="schema.profile.items.type_mismatch",
                message="'items' is only supported for array schemas",
                path=path + ("items",),
            )
        elif not isinstance(schema["items"], dict):
            _append_violation(
                violations,
                code="schema.profile.items.invalid",
                message="'items' must be a JSON object",
                path=path + ("items",),
            )
        else:
            _validate_schema_profile(schema["items"], violations, path=path + ("items",))

    raw_enum = schema.get("enum")
    if raw_enum is not None:
        if not isinstance(raw_enum, list) or not raw_enum:
            _append_violation(
                violations,
                code="schema.profile.enum.invalid",
                message="'enum' must be a non-empty array",
                path=path + ("enum",),
            )
        else:
            normalized = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in raw_enum]
            if len(set(normalized)) != len(normalized):
                _append_violation(
                    violations,
                    code="schema.profile.enum.duplicate",
                    message="'enum' contains duplicate values",
                    path=path + ("enum",),
                )

    if "const" in schema and raw_enum is not None and schema["const"] not in raw_enum:
        _append_violation(
            violations,
            code="schema.profile.const.enum_mismatch",
            message="'const' must be included in 'enum' when both are present",
            path=path + ("const",),
        )

    for keyword in STRING_KEYWORDS:
        if keyword in schema and schema_type != "string":
            _append_violation(
                violations,
                code="schema.profile.string_keyword.type_mismatch",
                message=f"'{keyword}' is only supported for string schemas",
                path=path + (keyword,),
            )

    for keyword in NUMERIC_KEYWORDS:
        if keyword in schema and schema_type not in {"integer", "number"}:
            _append_violation(
                violations,
                code="schema.profile.numeric_keyword.type_mismatch",
                message=f"'{keyword}' is only supported for integer/number schemas",
                path=path + (keyword,),
            )

    for keyword in ARRAY_KEYWORDS:
        if keyword in schema and schema_type != "array":
            _append_violation(
                violations,
                code="schema.profile.array_keyword.type_mismatch",
                message=f"'{keyword}' is only supported for array schemas",
                path=path + (keyword,),
            )

    if (
        "minLength" in schema
        and "maxLength" in schema
        and isinstance(schema["minLength"], int)
        and isinstance(schema["maxLength"], int)
        and schema["minLength"] > schema["maxLength"]
    ):
        _append_violation(
            violations,
            code="schema.profile.length.invalid_range",
            message="'minLength' cannot be greater than 'maxLength'",
            path=path,
        )

    if (
        "minimum" in schema
        and "maximum" in schema
        and isinstance(schema["minimum"], (int, float))
        and isinstance(schema["maximum"], (int, float))
        and schema["minimum"] > schema["maximum"]
    ):
        _append_violation(
            violations,
            code="schema.profile.numeric.invalid_range",
            message="'minimum' cannot be greater than 'maximum'",
            path=path,
        )

    if (
        "minItems" in schema
        and "maxItems" in schema
        and isinstance(schema["minItems"], int)
        and isinstance(schema["maxItems"], int)
        and schema["minItems"] > schema["maxItems"]
    ):
        _append_violation(
            violations,
            code="schema.profile.array.invalid_range",
            message="'minItems' cannot be greater than 'maxItems'",
            path=path,
        )

    if is_root:
        for extension_key in sorted(ROOT_EXTENSION_KEYS):
            _ensure_extension_list(schema, extension_key, properties, violations)


def validate_contract_schema(schema: JsonSchemaDocument) -> SchemaValidationResponse:
    violations: list[ValidationViolation] = []

    if not isinstance(schema, dict):
        _append_violation(
            violations,
            code="schema.document.invalid",
            message="Schema must be a JSON object",
        )
    else:
        try:
            validator_class = validator_for(schema)
            validator_class.check_schema(schema)
        except SchemaError as exc:
            _append_violation(
                violations,
                code="schema.metaschema.invalid",
                message=exc.message,
                path=(),
            )

        _validate_schema_profile(schema, violations, is_root=True)

    verdict = ValidationVerdict.FAIL if violations else ValidationVerdict.OK
    details = {
        "property_count": len(schema.get("properties", {})) if isinstance(schema, dict) else 0,
        "required_count": len(schema.get("required", [])) if isinstance(schema, dict) else 0,
        "extensions": sorted(key for key in ROOT_EXTENSION_KEYS if isinstance(schema, dict) and key in schema),
    }

    return SchemaValidationResponse(verdict=verdict, violations=violations, details=details)
