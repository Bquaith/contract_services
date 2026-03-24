from __future__ import annotations

import json
from typing import Any

from app.schemas.contract import JsonSchemaDocument

EXTENSION_KEYS = ["x-primaryKey", "x-businessKey"]


def _canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def build_schema_diff(
    base_schema: JsonSchemaDocument,
    candidate_schema: JsonSchemaDocument,
) -> dict[str, Any]:
    base_properties = base_schema.get("properties", {})
    candidate_properties = candidate_schema.get("properties", {})

    added_properties = sorted(set(candidate_properties) - set(base_properties))
    removed_properties = sorted(set(base_properties) - set(candidate_properties))

    changed_properties: list[dict[str, Any]] = []
    for name in sorted(set(base_properties) & set(candidate_properties)):
        if _canonical_json(base_properties[name]) != _canonical_json(candidate_properties[name]):
            changed_properties.append(
                {
                    "name": name,
                    "from": base_properties[name],
                    "to": candidate_properties[name],
                }
            )

    base_required = set(base_schema.get("required", []))
    candidate_required = set(candidate_schema.get("required", []))

    required_added = sorted(candidate_required - base_required)
    required_removed = sorted(base_required - candidate_required)

    additional_properties_changed = None
    if base_schema.get("additionalProperties", True) != candidate_schema.get("additionalProperties", True):
        additional_properties_changed = {
            "from": base_schema.get("additionalProperties", True),
            "to": candidate_schema.get("additionalProperties", True),
        }

    extensions_changed = None
    base_extensions = {key: base_schema.get(key, []) for key in EXTENSION_KEYS}
    candidate_extensions = {key: candidate_schema.get(key, []) for key in EXTENSION_KEYS}
    if base_extensions != candidate_extensions:
        extensions_changed = {
            "from": base_extensions,
            "to": candidate_extensions,
        }

    return {
        "added_properties": added_properties,
        "removed_properties": removed_properties,
        "changed_properties": changed_properties,
        "required_added": required_added,
        "required_removed": required_removed,
        "additional_properties_changed": additional_properties_changed,
        "extensions_changed": extensions_changed,
    }
