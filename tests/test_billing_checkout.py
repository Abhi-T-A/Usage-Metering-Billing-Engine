from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan
from app.models.tenant import Tenant


def test_checkout_unauthenticated_rejected(client: TestClient):
    """Unauthenticated requests to /billing/checkout must return 401."""
    response = client.post(
        "/billing/checkout",
        json={"plan_name": "PRO"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_checkout_nonexistent_plan_returns_404(
    client: TestClient,
    test_tenant_data: dict,
):
    """Requesting a plan that does not exist in the database returns 404."""
    response = client.post(
        "/billing/checkout",
        json={"plan_name": "NON_EXISTENT_ULTRA_PLAN"},
        headers=test_tenant_data["headers"],
    )
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_checkout_current_plan_returns_400(
    client: TestClient,
    test_tenant_data: dict,
):
    """Requesting the plan the tenant is already on returns 400."""
    # Test tenant is on TEST_FREE
    response = client.post(
        "/billing/checkout",
        json={"plan_name": "TEST_FREE"},
        headers=test_tenant_data["headers"],
    )
    assert response.status_code == 400
    assert "already subscribed" in response.json()["detail"].lower()


def test_checkout_success_and_plan_not_prematurely_updated(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """Valid checkout creates a Stripe session URL and does NOT change tenant plan in DB."""
    # 1. Create a paid PRO plan in database
    pro_plan = Plan(
        name="PRO",
        api_call_limit=10000,
        ai_token_limit=1000000,
        price_cents=2900,  # $29.00
    )
    db_session.add(pro_plan)
    db_session.commit()
    db_session.refresh(pro_plan)

    tenant_id = test_tenant_data["tenant"].id
    original_plan_id = test_tenant_data["tenant"].plan_id

    # 2. Mock Stripe checkout.Session.create
    mock_session = MagicMock()
    mock_session.url = "https://checkout.stripe.com/c/pay/cs_test_mock123"
    mock_session.id = "cs_test_mock123"

    with patch("stripe.checkout.Session.create", return_value=mock_session) as mock_create:
        response = client.post(
            "/billing/checkout",
            json={"plan_name": "PRO"},
            headers=test_tenant_data["headers"],
        )

        assert response.status_code == 201
        data = response.json()
        assert data["checkout_url"] == "https://checkout.stripe.com/c/pay/cs_test_mock123"
        assert data["session_id"] == "cs_test_mock123"
        assert data["plan_name"] == "PRO"

        # Verify Stripe API was called with exact metadata and amount
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["mode"] == "subscription"
        assert call_kwargs["metadata"]["tenant_id"] == str(tenant_id)
        assert call_kwargs["metadata"]["plan_id"] == str(pro_plan.id)
        assert call_kwargs["line_items"][0]["price_data"]["unit_amount"] == 2900

    # 3. Database Check: Tenant plan MUST NOT have changed yet
    refreshed_tenant = db_session.scalar(
        select(Tenant).where(Tenant.id == tenant_id)
    )
    assert refreshed_tenant.plan_id == original_plan_id
    assert refreshed_tenant.plan_id != pro_plan.id
