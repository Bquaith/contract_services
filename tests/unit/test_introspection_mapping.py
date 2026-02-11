import pytest

from app.schemas.enums import FieldType
from app.service.introspection import map_postgres_type


@pytest.mark.parametrize(
    ("data_type", "udt_name", "expected"),
    [
        ("character varying", "varchar", FieldType.STRING),
        ("text", "text", FieldType.STRING),
        ("integer", "int4", FieldType.INT),
        ("bigint", "int8", FieldType.INT),
        ("numeric", "numeric", FieldType.DECIMAL),
        ("decimal", "numeric", FieldType.DECIMAL),
        ("boolean", "bool", FieldType.BOOL),
        ("date", "date", FieldType.DATE),
        ("timestamp without time zone", "timestamp", FieldType.TIMESTAMP),
        ("timestamp with time zone", "timestamptz", FieldType.TIMESTAMP),
        ("json", "json", FieldType.JSON),
        ("jsonb", "jsonb", FieldType.JSON),
    ],
)
def test_map_postgres_type_supported(data_type: str, udt_name: str, expected: FieldType) -> None:
    assert map_postgres_type(data_type=data_type, udt_name=udt_name) == expected


def test_map_postgres_type_unsupported_returns_none() -> None:
    assert map_postgres_type(data_type="uuid", udt_name="uuid") is None
