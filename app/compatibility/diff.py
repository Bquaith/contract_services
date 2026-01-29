from typing import Any

from app.schemas.contract import ContractSchema, FieldSpec


def _field_projection(field: FieldSpec) -> dict[str, Any]:
    return {
        "type": field.type.value,
        "nullable": field.nullable,
        "default": field.default,
        "description": field.description,
        "pii_flag": field.pii_flag,
    }


def build_schema_diff(base_schema: ContractSchema, candidate_schema: ContractSchema) -> dict[str, Any]:
    base_fields = {field.name: field for field in base_schema.fields}
    candidate_fields = {field.name: field for field in candidate_schema.fields}

    added_fields = sorted(set(candidate_fields) - set(base_fields))
    removed_fields = sorted(set(base_fields) - set(candidate_fields))

    changed_fields: list[dict[str, Any]] = []
    for name in sorted(set(base_fields) & set(candidate_fields)):
        left = _field_projection(base_fields[name])
        right = _field_projection(candidate_fields[name])
        if left != right:
            changed_fields.append({"name": name, "from": left, "to": right})

    changed_keys = None
    left_keys = base_schema.keys.model_dump(mode="json")
    right_keys = candidate_schema.keys.model_dump(mode="json")
    if left_keys != right_keys:
        changed_keys = {"from": left_keys, "to": right_keys}

    changed_constraints = None
    if base_schema.constraints != candidate_schema.constraints:
        changed_constraints = {
            "from": base_schema.constraints,
            "to": candidate_schema.constraints,
        }

    return {
        "added_fields": added_fields,
        "removed_fields": removed_fields,
        "changed_fields": changed_fields,
        "changed_keys": changed_keys,
        "changed_constraints": changed_constraints,
    }
