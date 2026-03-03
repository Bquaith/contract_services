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
        "fields": [
            {"name": "order_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "int", "nullable": True},
        ],
        "keys": {
            "primary": ["order_id"],
            "business": ["order_id"],
            "partition": [],
            "hash_keys": ["order_id"],
        },
        "constraints": [],
        "description": "v1",
    }


def _schema_v2_breaking() -> dict[str, Any]:
    return {
        "fields": [
            {"name": "order_id", "type": "string", "nullable": False},
            {"name": "amount", "type": "int", "nullable": True},
            {"name": "source_system", "type": "string", "nullable": False},
        ],
        "keys": {
            "primary": ["order_id"],
            "business": ["order_id"],
            "partition": [],
            "hash_keys": ["order_id"],
        },
        "constraints": [],
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


def test_compatibility_endpoint(client: TestClient, write_headers: dict[str, str]) -> None:
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
            "schema": _schema_v2_breaking(),
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
    assert compatibility["verdict"] == "fail"
    assert any(item["code"] == "compatibility.backward.added_required" for item in compatibility["violations"])


def test_validate_schema_endpoint(client: TestClient, write_headers: dict[str, str]) -> None:
    response = client.post(
        "/validate/schema",
        json={"schema": _schema_v1()},
        headers=write_headers,
    )
    assert response.status_code == 200
    assert response.json()["verdict"] == "ok"
