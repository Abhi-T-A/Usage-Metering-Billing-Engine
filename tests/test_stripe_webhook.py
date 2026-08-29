import json
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
import stripe

from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.models.webhook_event import StripeWebhookEvent


def test_probe_3_checkout_session_completed_upgrades_tenant(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """PROBE 3 FOUNDATION — Verified checkout.session.completed upgrades tenant Free -> Pro.
    
    1. Tenant starts on TEST_FREE plan.
    2. Deliver verified checkout.session.completed event with PRO plan metadata.
    3. Assert webhook returns HTTP 200.
    4. Assert Tenant.plan_id in database is upgraded to PRO.
    5. Assert Subscription record in database is created with active status and Stripe IDs.
    """
    tenant = test_tenant_data["tenant"]
    original_plan_id = tenant.plan_id

    # Create PRO plan
    pro_plan = Plan(
        name="PRO",
        api_call_limit=10000,
        ai_token_limit=1000000,
        price_cents=2900,
    )
    db_session.add(pro_plan)
    db_session.commit()
    db_session.refresh(pro_plan)

    event_payload = {
        "id": "evt_test_checkout_completed_001",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_session_123",
                "customer": "cus_test_cust_456",
                "subscription": "sub_test_sub_789",
                "metadata": {
                    "tenant_id": str(tenant.id),
                    "plan_id": str(pro_plan.id),
                },
            }
        },
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")

    # Mock stripe.Webhook.construct_event to return the parsed dict/event
    with patch("stripe.Webhook.construct_event", return_value=event_payload):
        response = client.post(
            "/webhooks/stripe",
            content=raw_payload,
            headers={"Stripe-Signature": "t=123,v1=valid_signature_mock"},
        )

        assert response.status_code == 200
        assert response.json()["status"] == "success"
        assert response.json()["event_id"] == "evt_test_checkout_completed_001"

    # Database Assertions: Tenant upgraded from Free -> Pro
    refreshed_tenant = db_session.scalar(
        select(Tenant).where(Tenant.id == tenant.id)
    )
    assert refreshed_tenant.plan_id == pro_plan.id
    assert refreshed_tenant.plan_id != original_plan_id

    # Database Assertions: Subscription record created and active
    sub = db_session.scalar(
        select(Subscription).where(Subscription.tenant_id == tenant.id)
    )
    assert sub is not None
    assert sub.plan_id == pro_plan.id
    assert sub.status == "active"
    assert sub.stripe_customer_id == "cus_test_cust_456"
    assert sub.stripe_subscription_id == "sub_test_sub_789"


def test_probe_4_missing_signature_returns_400(client: TestClient):
    """PROBE 4 — Missing Stripe-Signature header returns 400 Bad Request."""
    response = client.post(
        "/webhooks/stripe",
        content=b'{"type": "checkout.session.completed"}',
    )
    assert response.status_code == 400
    assert "Stripe-Signature" in response.json()["detail"]


def test_probe_4_forged_signature_returns_400(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """PROBE 4 — Forged / invalid Stripe signature returns 400 and modifies NO database state."""
    tenant = test_tenant_data["tenant"]
    original_plan_id = tenant.plan_id

    with patch(
        "stripe.Webhook.construct_event",
        side_effect=stripe.error.SignatureVerificationError(
            "Signature verification failed", "bad_sig", "raw_body"
        ),
    ):
        response = client.post(
            "/webhooks/stripe",
            content=b'{"type": "checkout.session.completed"}',
            headers={"Stripe-Signature": "forged_signature_xyz"},
        )
        assert response.status_code == 400
        assert "Invalid Stripe signature" in response.json()["detail"]

    # Verify no state changes in database
    refreshed_tenant = db_session.scalar(
        select(Tenant).where(Tenant.id == tenant.id)
    )
    assert refreshed_tenant.plan_id == original_plan_id

    events = db_session.scalars(select(StripeWebhookEvent)).all()
    assert len(events) == 0


def test_probe_4_duplicate_webhook_processed_only_once(
    client: TestClient,
    db_session: Session,
    test_tenant_data: dict,
):
    """PROBE 4 — Delivering the exact same webhook twice is processed once and safely ignored on replay."""
    tenant = test_tenant_data["tenant"]

    pro_plan = Plan(
        name="PRO_DUP",
        api_call_limit=10000,
        ai_token_limit=1000000,
        price_cents=2900,
    )
    db_session.add(pro_plan)
    db_session.commit()

    event_payload = {
        "id": "evt_duplicate_test_001",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_dup_123",
                "customer": "cus_test_dup",
                "subscription": "sub_test_dup",
                "metadata": {
                    "tenant_id": str(tenant.id),
                    "plan_id": str(pro_plan.id),
                },
            }
        },
    }
    raw_payload = json.dumps(event_payload).encode("utf-8")

    with patch("stripe.Webhook.construct_event", return_value=event_payload):
        # 1. First Delivery
        resp_1 = client.post(
            "/webhooks/stripe",
            content=raw_payload,
            headers={"Stripe-Signature": "valid_sig"},
        )
        assert resp_1.status_code == 200
        assert resp_1.json()["status"] == "success"

        # 2. Second Delivery (Stripe Webhook Retry / Replay)
        resp_2 = client.post(
            "/webhooks/stripe",
            content=raw_payload,
            headers={"Stripe-Signature": "valid_sig"},
        )
        assert resp_2.status_code == 200
        assert resp_2.json()["status"] == "ignored"
        assert resp_2.json()["detail"] == "Event already processed"

    # Database Verification: Exactly ONE webhook event record exists
    recorded_events = db_session.scalars(
        select(StripeWebhookEvent).where(
            StripeWebhookEvent.stripe_event_id == "evt_duplicate_test_001"
        )
    ).all()
    assert len(recorded_events) == 1
    assert recorded_events[0].event_type == "checkout.session.completed"
