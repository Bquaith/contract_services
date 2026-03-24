from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.db.models import Contract, ContractVersion
from app.schemas.contract import JsonSchemaDocument
from app.schemas.enums import CompatibilityMode, ContractStatus, EntityType, VersionStatus
from app.schemas.introspection import IntrospectionRequest
from app.service.utils import calculate_checksum
from app.validators import validate_contract_schema


DEFAULT_INTROSPECT_VERSION = "0.1.0"
JSON_SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"


def map_postgres_type(data_type: str, udt_name: str) -> dict[str, Any] | None:
    normalized_data_type = data_type.lower().strip()
    normalized_udt_name = udt_name.lower().strip()

    if normalized_data_type in {"character varying", "character", "text"} or normalized_udt_name in {
        "varchar",
        "bpchar",
        "text",
    }:
        return {"type": "string"}

    if normalized_data_type in {"integer", "bigint", "smallint"} or normalized_udt_name in {
        "int2",
        "int4",
        "int8",
    }:
        return {"type": "integer"}

    if normalized_data_type in {"numeric", "decimal"} or normalized_udt_name == "numeric":
        return {"type": "number"}

    if normalized_data_type in {"real", "double precision"} or normalized_udt_name in {
        "float4",
        "float8",
    }:
        return {"type": "number"}

    if normalized_data_type == "boolean" or normalized_udt_name == "bool":
        return {"type": "boolean"}

    if normalized_data_type == "date" or normalized_udt_name == "date":
        return {"type": "string", "format": "date"}

    if normalized_data_type in {
        "timestamp without time zone",
        "timestamp with time zone",
    } or normalized_udt_name in {"timestamp", "timestamptz"}:
        return {"type": "string", "format": "date-time"}

    if normalized_data_type in {"json", "jsonb"} or normalized_udt_name in {"json", "jsonb"}:
        return {}

    return None


class IntrospectionService:
    def __init__(self, session: Session):
        self.session = session

    def introspect_table(self, payload: IntrospectionRequest, actor: str) -> tuple[Contract, ContractVersion]:
        if payload.entity_type != EntityType.TABLE:
            raise ApiError(
                status_code=422,
                code="unsupported_entity_type",
                message="Only entity_type='table' is supported for introspection",
                details={"entity_type": payload.entity_type.value},
            )

        remote_engine = create_engine(payload.connection_string, pool_pre_ping=True)
        try:
            if remote_engine.dialect.name != "postgresql":
                raise ApiError(
                    status_code=422,
                    code="unsupported_database",
                    message="Only PostgreSQL connection strings are supported",
                    details={"dialect": remote_engine.dialect.name},
                )

            properties, required_fields, primary_keys = self._load_table_structure(
                engine=remote_engine,
                schema_name=payload.source_schema,
                table_name=payload.table_name,
            )
        finally:
            remote_engine.dispose()

        schema_payload: JsonSchemaDocument = {
            "$schema": JSON_SCHEMA_DRAFT,
            "type": "object",
            "properties": properties,
            "required": required_fields,
            "additionalProperties": False,
            "description": f"Generated from {payload.source_schema}.{payload.table_name}",
            "x-primaryKey": primary_keys,
            "x-businessKey": [],
        }

        validation = validate_contract_schema(schema_payload)
        if validation.verdict.value == "fail":
            raise ApiError(
                status_code=422,
                code="schema_validation_failed",
                message="Generated schema is not valid",
                details={
                    "verdict": validation.verdict.value,
                    "violations": [item.model_dump(mode="json") for item in validation.violations],
                },
            )

        existing_stmt = select(Contract.id).where(
            Contract.namespace == payload.namespace,
            Contract.name == payload.name,
            Contract.deleted_at.is_(None),
        )
        if self.session.scalar(existing_stmt):
            raise ApiError(
                status_code=409,
                code="contract_already_exists",
                message="Contract with namespace/name already exists",
                details={"namespace": payload.namespace, "name": payload.name},
            )

        contract = Contract(
            namespace=payload.namespace,
            name=payload.name,
            entity_name=payload.table_name,
            entity_type=EntityType.TABLE,
            description=f"Introspected from {payload.source_schema}.{payload.table_name}",
            owners=[],
            tags=[],
            target_layer=payload.target_layer,
            status=ContractStatus.DRAFT,
            active_version=None,
        )

        version = ContractVersion(
            contract=contract,
            version=DEFAULT_INTROSPECT_VERSION,
            status=VersionStatus.DRAFT,
            schema_json=schema_payload,
            checksum=calculate_checksum(schema_payload),
            compatibility_mode=CompatibilityMode.BACKWARD,
            created_by=actor,
            is_locked=False,
        )

        try:
            self.session.add(contract)
            self.session.add(version)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise ApiError(
                status_code=409,
                code="contract_already_exists",
                message="Contract with namespace/name already exists",
                details={"namespace": payload.namespace, "name": payload.name},
            ) from exc

        self.session.refresh(contract)
        self.session.refresh(version)

        return contract, version

    def _load_table_structure(
        self,
        engine: Engine,
        schema_name: str,
        table_name: str,
    ) -> tuple[dict[str, JsonSchemaDocument], list[str], list[str]]:
        table_query = text(
            """
            SELECT 1
            FROM information_schema.tables t
            JOIN pg_catalog.pg_namespace n ON n.nspname = t.table_schema
            JOIN pg_catalog.pg_class c ON c.relname = t.table_name AND c.relnamespace = n.oid
            WHERE t.table_schema = :schema_name
              AND t.table_name = :table_name
              AND t.table_type = 'BASE TABLE'
              AND c.relkind = 'r'
            LIMIT 1
            """
        )

        columns_query = text(
            """
            SELECT
                c.column_name,
                c.data_type,
                c.udt_name,
                c.is_nullable
            FROM information_schema.columns c
            JOIN pg_catalog.pg_namespace n ON n.nspname = c.table_schema
            JOIN pg_catalog.pg_class pc ON pc.relname = c.table_name
                AND pc.relnamespace = n.oid
                AND pc.relkind = 'r'
            WHERE c.table_schema = :schema_name
              AND c.table_name = :table_name
            ORDER BY c.ordinal_position
            """
        )

        primary_keys_query = text(
            """
            SELECT a.attname AS column_name
            FROM pg_catalog.pg_index i
            JOIN pg_catalog.pg_class c ON c.oid = i.indrelid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_catalog.pg_attribute a
                ON a.attrelid = c.oid
                AND a.attnum = ANY(i.indkey)
            WHERE n.nspname = :schema_name
              AND c.relname = :table_name
              AND i.indisprimary
            ORDER BY array_position(i.indkey, a.attnum)
            """
        )

        with engine.connect() as connection:
            table_exists = connection.execute(
                table_query,
                {"schema_name": schema_name, "table_name": table_name},
            ).scalar()
            if not table_exists:
                raise ApiError(
                    status_code=404,
                    code="source_table_not_found",
                    message="Source table not found",
                    details={"schema": schema_name, "table_name": table_name},
                )

            rows = connection.execute(
                columns_query,
                {"schema_name": schema_name, "table_name": table_name},
            ).mappings()

            properties: dict[str, JsonSchemaDocument] = {}
            required_fields: list[str] = []
            for row in rows:
                mapped_type = map_postgres_type(
                    data_type=str(row["data_type"]),
                    udt_name=str(row["udt_name"]),
                )
                if mapped_type is None:
                    raise ApiError(
                        status_code=422,
                        code="unsupported_column_type",
                        message="Unsupported PostgreSQL type for contract mapping",
                        details={
                            "column": row["column_name"],
                            "data_type": row["data_type"],
                            "udt_name": row["udt_name"],
                        },
                    )

                column_name = str(row["column_name"])
                properties[column_name] = mapped_type
                if str(row["is_nullable"]).upper() != "YES":
                    required_fields.append(column_name)

            primary_key_rows = connection.execute(
                primary_keys_query,
                {"schema_name": schema_name, "table_name": table_name},
            ).mappings()
            primary_keys = [str(row["column_name"]) for row in primary_key_rows]

        return properties, required_fields, primary_keys
