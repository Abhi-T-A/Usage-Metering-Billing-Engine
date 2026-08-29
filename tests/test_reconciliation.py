from unittest.mock import MagicMock, patch
from sqlalchemy import select
from sqlalchemy.orm import Session
import stripe

from app.models.plan import Plan
from app.models.subscription import Subscription
from app.models.tenant import Tenant
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.tenant_repository import TenantRepository
from app.scripts.reconciliation_job import SubscriptionReconciler


def test_reconciliation_in_sync_makes_no_changes(
    db_session: Session,
    test_tenant_data: dict,
):
    """When local subscription state matches Stripe state, 0 updates are made."""
    tenant = test_tenant_data["tenant"]

    # Create local subscription
    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=tenant.plan_id,
        status="active",
        stripe_customer_id="cus_sync_1",
        stripe_subscription_id="sub_sync_1",
    )
    db_session.add(sub)
    db_session.commit()

    mock_stripe_sub = {
        "id": "sub_sync_1",
        "status": "active",
        "current_period_start": 1700000000,
        "current_period_end": 1702592000,
    }

    with patch("stripe.Subscription.retrieve", return_value=mock_stripe_sub):
        reconciler = SubscriptionReconciler(
            db=db_session,
            plan_repo=PlanRepository(db_session),
            tenant_repo=TenantRepository(db_session),
            subscription_repo=SubscriptionRepository(db_session),
        )
        stats = reconciler.reconcile_all()

        assert stats["total_checked"] == 1
        assert stats["updated"] == 1  # period timestamps updated
        assert stats["errors"] == 0

        # Run second time: now completely in-sync
        stats_2 = reconciler.reconcile_all()
        assert stats_2["in_sync"] == 1
        assert stats_2["updated"] == 0


def test_reconciliation_status_mismatch_correction(
    db_session: Session,
    test_tenant_data: dict,
):
    """When Stripe reports a canceled subscription, local state is updated and tenant downgraded."""
    tenant = test_tenant_data["tenant"]

    # Assign tenant to PRO plan first
    pro_plan = Plan(
        name="PRO",
        api_call_limit=10000,
        ai_token_limit=1000000,
        price_cents=2900,
    )
    db_session.add(pro_plan)
    db_session.commit()
    tenant.plan_id = pro_plan.id
    db_session.add(tenant)

    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=pro_plan.id,
        status="active",
        stripe_customer_id="cus_cancel_1",
        stripe_subscription_id="sub_cancel_1",
    )
    db_session.add(sub)
    db_session.commit()

    # Stripe reports subscription is canceled
    mock_stripe_sub = {
        "id": "sub_cancel_1",
        "status": "canceled",
        "current_period_start": None,
        "current_period_end": None,
    }

    with patch("stripe.Subscription.retrieve", return_value=mock_stripe_sub):
        reconciler = SubscriptionReconciler(
            db=db_session,
            plan_repo=PlanRepository(db_session),
            tenant_repo=TenantRepository(db_session),
            subscription_repo=SubscriptionRepository(db_session),
        )
        stats = reconciler.reconcile_all()

        assert stats["updated"] == 1
        assert stats["errors"] == 0

        # Assert local subscription is now canceled
        refreshed_sub = db_session.scalar(
            select(Subscription).where(Subscription.id == sub.id)
        )
        assert refreshed_sub.status == "canceled"

        # Assert tenant was downgraded to FREE plan
        refreshed_tenant = db_session.scalar(
            select(Tenant).where(Tenant.id == tenant.id)
        )
        assert refreshed_tenant.plan_id == test_tenant_data["plan"].id


def test_reconciliation_missing_stripe_subscription(
    db_session: Session,
    test_tenant_data: dict,
):
    """When Stripe returns 404 (resource missing), subscription is safely marked canceled."""
    tenant = test_tenant_data["tenant"]

    sub = Subscription(
        tenant_id=tenant.id,
        plan_id=tenant.plan_id,
        status="active",
        stripe_subscription_id="sub_missing_404",
    )
    db_session.add(sub)
    db_session.commit()

    with patch(
        "stripe.Subscription.retrieve",
        side_effect=stripe.error.InvalidRequestError("No such subscription", "id"),
    ):
        reconciler = SubscriptionReconciler(
            db=db_session,
            plan_repo=PlanRepository(db_session),
            tenant_repo=TenantRepository(db_session),
            subscription_repo=SubscriptionRepository(db_session),
        )
        stats = reconciler.reconcile_all()

        assert stats["updated"] == 1
        assert stats["errors"] == 0

        refreshed_sub = db_session.scalar(
            select(Subscription).where(Subscription.id == sub.id)
        )
        assert refreshed_sub.status == "canceled"


def test_reconciliation_error_isolation(
    db_session: Session,
    test_tenant_data: dict,
):
    """Failure on one subscription does NOT abort reconciliation of subsequent subscriptions."""
    tenant = test_tenant_data["tenant"]

    # Sub 1 (will fail Stripe call)
    sub_1 = Subscription(
        tenant_id=tenant.id,
        plan_id=tenant.plan_id,
        status="active",
        stripe_subscription_id="sub_fail_network",
    )
    # Sub 2 (will succeed)
    tenant_2 = Tenant(
        name="Second Tenant",
        plan_id=tenant.plan_id,
        api_key_hash="hash2",
    )
    db_session.add_all([sub_1, tenant_2])
    db_session.commit()

    sub_2 = Subscription(
        tenant_id=tenant_2.id,
        plan_id=tenant.plan_id,
        status="active",
        stripe_subscription_id="sub_success_sync",
    )
    db_session.add(sub_2)
    db_session.commit()

    def side_effect_retrieve(sub_id):
        if sub_id == "sub_fail_network":
            raise stripe.error.APIConnectionError("Connection timed out")
        return {
            "id": sub_id,
            "status": "canceled",
            "current_period_start": None,
            "current_period_end": None,
        }

    with patch("stripe.Subscription.retrieve", side_effect=side_effect_retrieve):
        reconciler = SubscriptionReconciler(
            db=db_session,
            plan_repo=PlanRepository(db_session),
            tenant_repo=TenantRepository(db_session),
            subscription_repo=SubscriptionRepository(db_session),
        )
        stats = reconciler.reconcile_all()

        assert stats["total_checked"] == 2
        assert stats["errors"] == 1
        assert stats["updated"] == 1

        # Verify sub_2 was updated despite sub_1 failing
        refreshed_sub_2 = db_session.scalar(
            select(Subscription).where(Subscription.id == sub_2.id)
        )
        assert refreshed_sub_2.status == "canceled"
