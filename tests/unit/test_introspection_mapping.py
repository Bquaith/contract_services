import pytest

from app.service.introspection import map_postgres_type


@pytest.mark.parametrize(
    ("data_type", "udt_name", "expected"),
    [
        ("character varying", "varchar", {"type": "string"}),
        ("text", "text", {"type": "string"}),
        ("integer", "int4", {"type": "integer"}),
        ("bigint", "int8", {"type": "integer"}),
        ("numeric", "numeric", {"type": "number"}),
        ("decimal", "numeric", {"type": "number"}),
        ("real", "float4", {"type": "number"}),
        ("double precision", "float8", {"type": "number"}),
        ("boolean", "bool", {"type": "boolean"}),
        ("date", "date", {"type": "string", "format": "date"}),
        ("timestamp without time zone", "timestamp", {"type": "string", "format": "date-time"}),
        ("timestamp with time zone", "timestamptz", {"type": "string", "format": "date-time"}),
        ("json", "json", {}),
        ("jsonb", "jsonb", {}),
    ],
)
def test_map_postgres_type_supported(data_type: str, udt_name: str, expected: dict) -> None:
    assert map_postgres_type(data_type=data_type, udt_name=udt_name) == expected


def test_map_postgres_type_unsupported_returns_none() -> None:
    assert map_postgres_type(data_type="uuid", udt_name="uuid") is None
