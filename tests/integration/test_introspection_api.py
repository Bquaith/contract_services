from __future__ import annotations

from sqlalchemy import text


def test_introspect_table_creates_draft_contract_and_version(
    client,
    write_headers: dict[str, str],
    test_database_url: str,
    db_session_factory,
) -> None:
    table_name = "source_orders_introspect"
    create_sql = f"""
        CREATE TABLE public.{table_name} (
            id BIGINT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            amount NUMERIC(12,2),
            created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL,
            event_date DATE,
            is_active BOOLEAN NOT NULL,
            payload JSONB
        )
    """

    session = db_session_factory()
    try:
        session.execute(text(f"DROP TABLE IF EXISTS public.{table_name}"))
        session.execute(text(create_sql))
        session.commit()
    finally:
        session.close()

    try:
        response = client.post(
            "/introspect",
            json={
                "connection_string": test_database_url,
                "schema": "public",
                "table_name": table_name,
                "namespace": "erp",
                "name": "orders_contract_generated",
                "entity_type": "table",
                "target_layer": "raw",
            },
            headers=write_headers,
        )

        assert response.status_code == 201
        payload = response.json()

        assert payload["contract"]["status"] == "draft"
        assert payload["contract"]["active_version"] is None
        assert payload["version"]["version"] == "0.1.0"
        assert payload["version"]["status"] == "draft"
        assert payload["version"]["created_by"] == "pytest"

        schema_json = payload["version"]["schema_json"]
        fields = {field["name"]: field for field in schema_json["fields"]}
        assert fields["id"]["type"] == "int"
        assert fields["customer_name"]["type"] == "string"
        assert fields["amount"]["type"] == "decimal"
        assert fields["created_at"]["type"] == "timestamp"
        assert fields["event_date"]["type"] == "date"
        assert fields["is_active"]["type"] == "bool"
        assert fields["payload"]["type"] == "json"

        assert schema_json["keys"]["primary"] == ["id"]
        assert schema_json["keys"]["business"] == []
        assert schema_json["keys"]["hash_keys"] == []
    finally:
        drop_session = db_session_factory()
        try:
            drop_session.execute(text(f"DROP TABLE IF EXISTS public.{table_name}"))
            drop_session.commit()
        finally:
            drop_session.close()


def test_introspect_returns_404_when_table_not_found(
    client,
    write_headers: dict[str, str],
    test_database_url: str,
) -> None:
    response = client.post(
        "/introspect",
        json={
            "connection_string": test_database_url,
            "schema": "public",
            "table_name": "missing_table_for_introspection",
            "namespace": "erp",
            "name": "missing_contract",
            "entity_type": "table",
            "target_layer": "raw",
        },
        headers=write_headers,
    )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "source_table_not_found"


def test_introspect_returns_409_when_contract_exists(
    client,
    write_headers: dict[str, str],
    test_database_url: str,
    db_session_factory,
) -> None:
    table_name = "source_orders_conflict"
    session = db_session_factory()
    try:
        session.execute(text(f"DROP TABLE IF EXISTS public.{table_name}"))
        session.execute(text(f"CREATE TABLE public.{table_name} (id BIGINT PRIMARY KEY)"))
        session.commit()
    finally:
        session.close()

    try:
        create_contract_resp = client.post(
            "/contracts",
            json={
                "namespace": "erp",
                "name": "existing_contract",
                "entity_name": "manual_table",
                "entity_type": "table",
                "description": "manual",
                "owners": [],
                "tags": [],
                "target_layer": "raw",
            },
            headers=write_headers,
        )
        assert create_contract_resp.status_code == 201

        introspect_resp = client.post(
            "/introspect",
            json={
                "connection_string": test_database_url,
                "schema": "public",
                "table_name": table_name,
                "namespace": "erp",
                "name": "existing_contract",
                "entity_type": "table",
                "target_layer": "raw",
            },
            headers=write_headers,
        )
        assert introspect_resp.status_code == 409
        assert introspect_resp.json()["error"]["code"] == "contract_already_exists"
    finally:
        cleanup_session = db_session_factory()
        try:
            cleanup_session.execute(text(f"DROP TABLE IF EXISTS public.{table_name}"))
            cleanup_session.commit()
        finally:
            cleanup_session.close()
