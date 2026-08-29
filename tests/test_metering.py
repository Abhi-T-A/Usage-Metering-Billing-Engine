from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.usage_event import UsageEvent


def test_probe_1_idempotent_usage_recording(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """PROBE 1 — Send the same billable request twice with one idempotency key.
    
    Expected:
    1. First request returns HTTP 201 with is_duplicate = False.
    2. Second request returns HTTP 200 with is_duplicate = True.
    3. Both responses reference the EXACT same usage event ID and metadata.
    4. Exactly ONE UsageEvent row exists in the database.
    5. Total usage is counted only once (no double counting).
    """
    headers = {
        **test_tenant_data["headers"],
        "Idempotency-Key": "idemp-key-probe-001",
    }
    payload = {
        "type": "API_CALL",
        "quantity": 1,
    }

    # First request
    response_1 = client.post("/generate", json=payload, headers=headers)
    assert response_1.status_code == 201
    data_1 = response_1.json()
    assert data_1["is_duplicate"] is False
    assert data_1["quantity"] == 1
    assert data_1["type"] == "API_CALL"
    assert data_1["idempotency_key"] == "idemp-key-probe-001"
    event_id = data_1["id"]

    # Second identical request (network retry / replay)
    response_2 = client.post("/generate", json=payload, headers=headers)
    assert response_2.status_code == 200
    data_2 = response_2.json()
    assert data_2["is_duplicate"] is True
    assert data_2["id"] == event_id
    assert data_2["created_at"] == data_1["created_at"]
    assert data_2["quantity"] == 1

    # Database Verification: Exactly 1 record exists in table
    tenant = test_tenant_data["tenant"]
    events = db_session.scalars(
        select(UsageEvent).where(
            UsageEvent.tenant_id == tenant.id,
            UsageEvent.idempotency_key == "idemp-key-probe-001",
        )
    ).all()
    assert len(events) == 1
    assert events[0].id == event_id
    assert events[0].quantity == 1


def test_idempotency_different_keys_creates_distinct_events(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """Verifies that requests with distinct idempotency keys create separate usage events."""
    headers_1 = {**test_tenant_data["headers"], "Idempotency-Key": "idemp-diff-001"}
    headers_2 = {**test_tenant_data["headers"], "Idempotency-Key": "idemp-diff-002"}
    payload = {"type": "API_CALL", "quantity": 1}

    resp_1 = client.post("/generate", json=payload, headers=headers_1)
    resp_2 = client.post("/generate", json=payload, headers=headers_2)

    assert resp_1.status_code == 201
    assert resp_2.status_code == 201
    assert resp_1.json()["id"] != resp_2.json()["id"]

    # Database count check
    tenant = test_tenant_data["tenant"]
    total_events = db_session.scalars(
        select(UsageEvent).where(UsageEvent.tenant_id == tenant.id)
    ).all()
    assert len(total_events) == 2


def test_generate_missing_idempotency_key_returns_400(
    client: TestClient,
    test_tenant_data: dict,
):
    """Missing Idempotency-Key header must return HTTP 400 Bad Request."""
    response = client.post(
        "/generate",
        json={"type": "API_CALL", "quantity": 1},
        headers=test_tenant_data["headers"],  # No Idempotency-Key
    )
    assert response.status_code == 400
    assert "Idempotency-Key" in response.json()["detail"]


def test_generate_missing_or_invalid_auth_returns_401(client: TestClient):
    """Missing or invalid API key must return HTTP 401 Unauthorized."""
    # Case 1: Missing API Key
    resp_missing = client.post(
        "/generate",
        json={"type": "API_CALL", "quantity": 1},
        headers={"Idempotency-Key": "some-key"},
    )
    assert resp_missing.status_code == 401
    assert resp_missing.json()["detail"] == "Missing API key"

    # Case 2: Invalid API Key
    resp_invalid = client.post(
        "/generate",
        json={"type": "API_CALL", "quantity": 1},
        headers={
            "X-API-Key": "invalid-non-existent-key",
            "Idempotency-Key": "some-key",
        },
    )
    assert resp_invalid.status_code == 401
    assert resp_invalid.json()["detail"] == "Invalid API key"
