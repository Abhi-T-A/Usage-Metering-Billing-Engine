from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.subscription import Subscription


class SubscriptionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_tenant_id(self, tenant_id: int) -> Subscription | None:
        """Finds the subscription associated with a tenant."""
        return self.db.scalar(
            select(Subscription).where(Subscription.tenant_id == tenant_id)
        )

    def get_by_stripe_subscription_id(
        self,
        stripe_subscription_id: str,
    ) -> Subscription | None:
        """Finds a subscription by its Stripe subscription ID."""
        return self.db.scalar(
            select(Subscription).where(
                Subscription.stripe_subscription_id == stripe_subscription_id
            )
        )

    def list_tracked_subscriptions(self) -> list[Subscription]:
        """Lists all subscriptions that have a connected Stripe subscription ID."""
        return list(
            self.db.scalars(
                select(Subscription).where(
                    Subscription.stripe_subscription_id.is_not(None)
                )
            ).all()
        )

    def create_or_update(
        self,
        tenant_id: int,
        plan_id: int,
        status: str,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        current_period_start: datetime | None = None,
        current_period_end: datetime | None = None,
    ) -> Subscription:
        """Creates or updates a subscription record for a tenant."""
        sub = self.get_by_tenant_id(tenant_id)
        if not sub:
            sub = Subscription(
                tenant_id=tenant_id,
                plan_id=plan_id,
                status=status,
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
                current_period_start=current_period_start,
                current_period_end=current_period_end,
            )
            self.db.add(sub)
        else:
            sub.plan_id = plan_id
            sub.status = status
            if stripe_customer_id:
                sub.stripe_customer_id = stripe_customer_id
            if stripe_subscription_id:
                sub.stripe_subscription_id = stripe_subscription_id
            if current_period_start:
                sub.current_period_start = current_period_start
            if current_period_end:
                sub.current_period_end = current_period_end
            self.db.add(sub)

        self.db.flush()
        self.db.refresh(sub)
        return sub
