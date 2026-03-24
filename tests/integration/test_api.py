from typing import Any

from fastapi.testclient import TestClient


def _contract_payload(namespace: str = "sales", name: str = "orders") -> dict[str, Any]:
    return {
        "namespace": namespace,
        "name": name,
        "entity_name": "orders_table",
        "entity_type": "table",
        "description": "Orders data contract",
        "owners": ["data-platform@company.local"],
        "tags": ["finance", "orders"],
        "target_layer": "curated",
    }


def _schema_v1() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "amount": {"type": "integer"},
        },
        "required": ["order_id"],
        "additionalProperties": False,
        "x-primaryKey": ["order_id"],
        "x-businessKey": ["order_id"],
        "description": "v1",
    }


def _schema_minor() -> dict[str, Any]:
    return {
        **_schema_v1(),
        "properties": {
            **_schema_v1()["properties"],
            "comment": {"type": "string"},
        },
        "description": "v1.1",
    }


def _schema_major_breaking() -> dict[str, Any]:
    return {
        **_schema_v1(),
        "properties": {
            **_schema_v1()["properties"],
            "source_system": {"type": "string"},
        },
        "required": ["order_id", "source_system"],
        "description": "v2",
    }


def test_health_endpoint(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_non_get_requires_api_key(client: TestClient) -> None:
    response = client.post("/contracts", json=_contract_payload())
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "unauthorized"


def test_contract_lifecycle_and_publish(client: TestClient, write_headers: dict[str, str]) -> None:
    create_contract_resp = client.post("/contracts", json=_contract_payload(), headers=write_headers)
    assert create_contract_resp.status_code == 201
    contract_id = create_contract_resp.json()["id"]

    create_version_resp = client.post(
        f"/contracts/{contract_id}/versions",
        json={
            "version": "1.0.0",
            "schema": _schema_v1(),
            "compatibility_mode": "backward",
        },
        headers=write_headers,
    )
    assert create_version_resp.status_code == 201

    promote_resp = client.post(
        f"/contracts/{contract_id}/versions/1.0.0/promote",
        headers=write_headers,
    )
    assert promote_resp.status_code == 200
    assert promote_resp.json()["status"] == "stable"

    active_resp = client.get("/contracts/sales/orders/active")
    assert active_resp.status_code == 200
    active_payload = active_resp.json()

    assert active_payload["contract"]["active_version"] == "1.0.0"
    assert active_payload["version"]["version"] == "1.0.0"


def test_minor_version_requires_backward_compatibility(client: TestClient, write_headers: dict[str, str]) -> None:
    create_contract_resp = client.post(
        "/contracts",
        json=_contract_payload(namespace="sales", name="payments"),
        headers=write_headers,
    )
    assert create_contract_resp.status_code == 201
    contract_id = create_contract_resp.json()["id"]

    v1_resp = client.post(
        f"/contracts/{contract_id}/versions",
        json={"version": "1.0.0", "schema": _schema_v1(), "compatibility_mode": "backward"},
        headers=write_headers,
    )
    assert v1_resp.status_code == 201

    promote_resp = client.post(
        f"/contracts/{contract_id}/versions/1.0.0/promote",
        headers=write_headers,
    )
    assert promote_resp.status_code == 200

    v2_resp = client.post(
        f"/contracts/{contract_id}/versions",
        json={
            "version": "1.1.0",
            "schema": _schema_minor(),
            "compatibility_mode": "backward",
        },
        headers=write_headers,
    )
    assert v2_resp.status_code == 201

    compatibility_resp = client.post(
        f"/contracts/{contract_id}/versions/1.1.0/compatibility",
        json={"mode": "backward"},
        headers=write_headers,
    )
    assert compatibility_resp.status_code == 200

    compatibility = compatibility_resp.json()
    assert compatibility["version_bump"] == "minor"
    assert compatibility["backward_compatible"] is True
    assert compatibility["forward_compatible"] is False
    assert compatibility["full_compatible"] is False
    assert compatibility["policy_passed"] is True
    assert compatibility["verdict"] == "ok"


def test_patch_version_rejects_non_full_compatibility(
    client: TestClient,
    write_headers: dict[str, str],
) -> None:
    create_contract_resp = client.post(
        "/contracts",
        json=_contract_payload(namespace="sales", name="ledger"),
        headers=write_headers,
    )
    assert create_contract_resp.status_code == 201
    contract_id = create_contract_resp.json()["id"]

    v1_resp = client.post(
        f"/contracts/{contract_id}/versions",
        json={"version": "1.0.0", "schema": _schema_v1(), "compatibility_mode": "backward"},
        headers=write_headers,
    )
    assert v1_resp.status_code == 201

    patch_resp = client.post(
        f"/contracts/{contract_id}/versions",
        json={
            "version": "1.0.1",
            "schema": _schema_minor(),
            "compatibility_mode": "backward",
        },
        headers=write_headers,
    )
    assert patch_resp.status_code == 409
    body = patch_resp.json()
    assert body["error"]["code"] == "version_policy_violation"
    assert body["error"]["details"]["version_bump"] == "patch"


def test_major_version_allows_breaking_change(client: TestClient, write_headers: dict[str, str]) -> None:
    create_contract_resp = client.post(
        "/contracts",
        json=_contract_payload(namespace="sales", name="shipments"),
        headers=write_headers,
    )
    assert create_contract_resp.status_code == 201
    contract_id = create_contract_resp.json()["id"]

    v1_resp = client.post(
        f"/contracts/{contract_id}/versions",
        json={"version": "1.0.0", "schema": _schema_v1(), "compatibility_mode": "backward"},
        headers=write_headers,
    )
    assert v1_resp.status_code == 201

    major_resp = client.post(
        f"/contracts/{contract_id}/versions",
        json={
            "version": "2.0.0",
            "schema": _schema_major_breaking(),
            "compatibility_mode": "backward",
        },
        headers=write_headers,
    )
    assert major_resp.status_code == 201


def test_validate_schema_endpoint(client: TestClient, write_headers: dict[str, str]) -> None:
    response = client.post(
        "/validate/schema",
        json={"schema": _schema_v1()},
        headers=write_headers,
    )
    assert response.status_code == 200
    assert response.json()["verdict"] == "ok"
