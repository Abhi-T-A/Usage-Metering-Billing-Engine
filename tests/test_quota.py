from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.usage_event import UsageEvent


def test_probe_2_quota_boundary_exact_limit_and_exceeded(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """PROBE 2 — Drive a tenant to exact quota boundary mathematically.
    
    Setup:
    - Test plan limit = 10 API calls.
    - Drive tenant to 9 calls used (remaining quota = 1).
    
    Steps:
    1. Send request with quantity = 1 (reaches exactly 10/10).
       -> Expected: HTTP 201 Created, total usage == 10.
    2. Send subsequent request with quantity = 1 (would require 11/10).
       -> Expected: HTTP 429 Too Many Requests.
       -> Response body contains structured quota info: current_usage=10, requested_quantity=1, limit=10.
    3. Database check: Verify NO event was created for the rejected request.
    4. Database check: Total usage in DB remains strictly 10.
    """
    tenant = test_tenant_data["tenant"]
    api_headers = test_tenant_data["headers"]

    # Step 0: Pre-consume 9 API calls (9/10 used)
    pre_event = UsageEvent(
        tenant_id=tenant.id,
        type="API_CALL",
        quantity=9,
        idempotency_key="pre-fill-usage-9",
    )
    db_session.add(pre_event)
    db_session.commit()

    # Step 1: Request reaching EXACT quota boundary (9 + 1 = 10 / 10)
    boundary_headers = {**api_headers, "Idempotency-Key": "key-boundary-10"}
    resp_boundary = client.post(
        "/generate",
        json={"type": "API_CALL", "quantity": 1},
        headers=boundary_headers,
    )
    assert resp_boundary.status_code == 201
    boundary_data = resp_boundary.json()
    assert boundary_data["is_duplicate"] is False
    assert boundary_data["quantity"] == 1

    # Verify total usage is now exactly 10
    events = db_session.scalars(
        select(UsageEvent).where(UsageEvent.tenant_id == tenant.id)
    ).all()
    total_usage = sum(e.quantity for e in events if e.type == "API_CALL")
    assert total_usage == 10

    # Step 2: Request after quota is exhausted (10 + 1 = 11 > 10)
    over_limit_headers = {**api_headers, "Idempotency-Key": "key-over-limit-11"}
    resp_over = client.post(
        "/generate",
        json={"type": "API_CALL", "quantity": 1},
        headers=over_limit_headers,
    )
    assert resp_over.status_code == 429
    error_body = resp_over.json()
    assert error_body["usage_type"] == "API_CALL"
    assert error_body["current_usage"] == 10
    assert error_body["requested_quantity"] == 1
    assert error_body["limit"] == 10
    assert "quota exceeded" in error_body["detail"].lower()

    # Step 3: Verify rejection did NOT persist any usage event
    rejected_event = db_session.scalar(
        select(UsageEvent).where(
            UsageEvent.tenant_id == tenant.id,
            UsageEvent.idempotency_key == "key-over-limit-11",
        )
    )
    assert rejected_event is None

    # Step 4: Verify total database usage is still strictly 10
    events_after = db_session.scalars(
        select(UsageEvent).where(UsageEvent.tenant_id == tenant.id)
    ).all()
    total_usage_after = sum(e.quantity for e in events_after if e.type == "API_CALL")
    assert total_usage_after == 10


def test_quota_idempotent_retry_at_quota_limit_succeeds(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """When a tenant has reached 100% quota, retrying the boundary request with the same
    Idempotency-Key MUST succeed (HTTP 200) rather than failing with 429.
    """
    tenant = test_tenant_data["tenant"]
    api_headers = test_tenant_data["headers"]

    # Pre-fill usage to 9
    pre_event = UsageEvent(
        tenant_id=tenant.id,
        type="API_CALL",
        quantity=9,
        idempotency_key="pre-fill-9",
    )
    db_session.add(pre_event)
    db_session.commit()

    # Execute 10th call (boundary)
    boundary_headers = {**api_headers, "Idempotency-Key": "key-call-10"}
    resp_1 = client.post(
        "/generate",
        json={"type": "API_CALL", "quantity": 1},
        headers=boundary_headers,
    )
    assert resp_1.status_code == 201

    # Retry 10th call when tenant is at full quota (10/10)
    resp_retry = client.post(
        "/generate",
        json={"type": "API_CALL", "quantity": 1},
        headers=boundary_headers,
    )
    assert resp_retry.status_code == 200
    assert resp_retry.json()["is_duplicate"] is True
    assert resp_retry.json()["id"] == resp_1.json()["id"]


def test_single_request_exceeding_total_limit_rejected(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """A fresh tenant requesting a quantity greater than total plan limit in a single call."""
    headers = {**test_tenant_data["headers"], "Idempotency-Key": "key-oversized"}
    resp = client.post(
        "/generate",
        json={"type": "API_CALL", "quantity": 25},  # Limit is 10
        headers=headers,
    )
    assert resp.status_code == 429
    assert resp.json()["current_usage"] == 0
    assert resp.json()["requested_quantity"] == 25
    assert resp.json()["limit"] == 10
