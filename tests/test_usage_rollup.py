from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_api_key
from app.models.plan import Plan
from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent


def test_get_usage_unauthenticated_returns_401(client: TestClient):
    """Calling GET /usage without an API key must return 401 Unauthorized."""
    response = client.get("/usage")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_get_usage_empty_returns_zeroes_with_plan_limits(
    client: TestClient,
    test_tenant_data: dict,
):
    """Fresh tenant with 0 usage receives used=0, remaining=limit, and cost=0."""
    response = client.get("/usage", headers=test_tenant_data["headers"])
    assert response.status_code == 200
    data = response.json()

    assert data["tenant_id"] == test_tenant_data["tenant"].id
    assert data["plan_name"] == "TEST_FREE"
    assert data["api_calls"]["used"] == 0
    assert data["api_calls"]["limit"] == 10
    assert data["api_calls"]["remaining"] == 10
    assert data["ai_tokens"]["used"] == 0
    assert data["ai_tokens"]["limit"] == 1000
    assert data["ai_tokens"]["remaining"] == 1000
    assert data["cost"]["total_cost_microcents"] == 0
    assert data["cost"]["total_cost_cents"] == 0


def test_get_usage_aggregates_categories_and_calculates_cost(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """Verifies that multiple usage events across categories aggregate correctly into GET /usage."""
    tenant = test_tenant_data["tenant"]

    # 1. Add API call events (3 calls)
    db_session.add(UsageEvent(tenant_id=tenant.id, type="API_CALL", quantity=2, idempotency_key="e1"))
    db_session.add(UsageEvent(tenant_id=tenant.id, type="API_CALL", quantity=1, idempotency_key="e2"))

    # 2. Add granular AI token events:
    # 500 normal input, 200 cached input, 100 output, 50 reasoning -> 850 total tokens
    db_session.add(UsageEvent(tenant_id=tenant.id, type="INPUT_TOKENS", quantity=500, idempotency_key="e3"))
    db_session.add(UsageEvent(tenant_id=tenant.id, type="CACHED_INPUT_TOKENS", quantity=200, idempotency_key="e4"))
    db_session.add(UsageEvent(tenant_id=tenant.id, type="OUTPUT_TOKENS", quantity=100, idempotency_key="e5"))
    db_session.add(UsageEvent(tenant_id=tenant.id, type="REASONING_TOKENS", quantity=50, idempotency_key="e6"))
    db_session.commit()

    response = client.get("/usage", headers=test_tenant_data["headers"])
    assert response.status_code == 200
    data = response.json()

    # Metric assertions
    assert data["api_calls"]["used"] == 3
    assert data["api_calls"]["limit"] == 10
    assert data["api_calls"]["remaining"] == 7

    assert data["ai_tokens"]["used"] == 850
    assert data["ai_tokens"]["limit"] == 1000
    assert data["ai_tokens"]["remaining"] == 150

    # Pricing calculation check (standard baseline rates):
    # input: 500 * 150 = 75,000 microcents
    # cached input: 200 * 38 = 7,600 microcents
    # output: 100 * 600 = 60,000 microcents
    # reasoning: 50 * 600 = 30,000 microcents
    # api calls: 3 * 0 = 0 microcents
    # total = 75,000 + 7,600 + 60,000 + 30,000 = 172,600 microcents
    # total cents = ceil(172,600 / 10,000) = 18 cents
    assert data["cost"]["total_cost_microcents"] == 172_600
    assert data["cost"]["total_cost_cents"] == 18


def test_get_usage_tenant_isolation(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
    test_plan: Plan,
):
    """Tenant A must never see Tenant B's usage events in GET /usage."""
    tenant_a = test_tenant_data["tenant"]

    # Create Tenant B
    raw_key_b = "tenant-b-secret-api-key"
    tenant_b = Tenant(
        name="Tenant B",
        plan_id=test_plan.id,
        api_key_hash=hash_api_key(raw_key_b),
    )
    db_session.add(tenant_b)
    db_session.commit()

    # Add usage for Tenant A (2 calls)
    db_session.add(UsageEvent(tenant_id=tenant_a.id, type="API_CALL", quantity=2, idempotency_key="a-1"))
    # Add usage for Tenant B (7 calls)
    db_session.add(UsageEvent(tenant_id=tenant_b.id, type="API_CALL", quantity=7, idempotency_key="b-1"))
    db_session.commit()

    # Query as Tenant A
    resp_a = client.get("/usage", headers={"X-API-Key": test_tenant_data["api_key"]})
    assert resp_a.status_code == 200
    assert resp_a.json()["tenant_id"] == tenant_a.id
    assert resp_a.json()["api_calls"]["used"] == 2
    assert resp_a.json()["api_calls"]["remaining"] == 8

    # Query as Tenant B
    resp_b = client.get("/usage", headers={"X-API-Key": raw_key_b})
    assert resp_b.status_code == 200
    assert resp_b.json()["tenant_id"] == tenant_b.id
    assert resp_b.json()["api_calls"]["used"] == 7
    assert resp_b.json()["api_calls"]["remaining"] == 3


def test_get_usage_remaining_at_exact_limit(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """When usage reaches or exceeds limit, remaining quota is strictly 0 (never negative)."""
    tenant = test_tenant_data["tenant"]

    # Consume exact limit (10 calls)
    db_session.add(UsageEvent(tenant_id=tenant.id, type="API_CALL", quantity=10, idempotency_key="lim-10"))
    db_session.commit()

    response = client.get("/usage", headers=test_tenant_data["headers"])
    assert response.status_code == 200
    data = response.json()
    assert data["api_calls"]["used"] == 10
    assert data["api_calls"]["limit"] == 10
    assert data["api_calls"]["remaining"] == 0
