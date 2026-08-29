from datetime import datetime, timezone
from typing import Any
import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.webhook_event_repository import WebhookEventRepository


class WebhookService:
    def __init__(
        self,
        db: Session,
        webhook_event_repo: WebhookEventRepository,
        tenant_repo: TenantRepository,
        subscription_repo: SubscriptionRepository,
        plan_repo: PlanRepository | None = None,
        webhook_secret: str | None = None,
    ) -> None:
        self.db = db
        self.webhook_event_repo = webhook_event_repo
        self.tenant_repo = tenant_repo
        self.subscription_repo = subscription_repo
        self.plan_repo = plan_repo or PlanRepository(db)
        self.webhook_secret = webhook_secret or settings.stripe_webhook_secret

    def verify_and_construct_event(
        self,
        payload: bytes,
        sig_header: str,
    ) -> stripe.Event:
        """Cryptographically verifies the Stripe signature against the raw payload bytes."""
        return stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=self.webhook_secret,
        )

    def fallback_tenant_to_free(self, tenant_id: int) -> None:
        """Helper to downgrade a tenant to FREE plan upon cancellation."""
        free_plan = self.plan_repo.get_by_name("FREE") or self.plan_repo.get_by_name("TEST_FREE")
        if free_plan:
            self.tenant_repo.update_plan(tenant_id=tenant_id, plan_id=free_plan.id)

    def process_event(self, event: Any) -> dict[str, Any]:
        """Atomically processes a verified Stripe webhook event with deduplication.
        
        Handles:
        - checkout.session.completed: Upgrades tenant plan & creates active Subscription
        - customer.subscription.updated: Syncs subscription status & billing dates
        - customer.subscription.deleted: Marks subscription canceled & downgrades tenant to FREE
        """
        event_id = event["id"] if isinstance(event, dict) else event.id
        event_type = event["type"] if isinstance(event, dict) else event.type

        # 1. Deduplication check
        existing_event = self.webhook_event_repo.get_by_event_id(event_id)
        if existing_event:
            return {
                "status": "ignored",
                "event_id": event_id,
                "detail": "Event already processed",
            }

        # 2. Event Dispatching
        if event_type == "checkout.session.completed":
            session = (
                event["data"]["object"]
                if isinstance(event, dict)
                else event.data.object
            )
            metadata = (
                session.get("metadata", {})
                if isinstance(session, dict)
                else getattr(session, "metadata", {})
            )

            tenant_id_val = (
                metadata.get("tenant_id")
                if isinstance(metadata, dict)
                else getattr(metadata, "tenant_id", None)
            )
            plan_id_val = (
                metadata.get("plan_id")
                if isinstance(metadata, dict)
                else getattr(metadata, "plan_id", None)
            )

            if not tenant_id_val or not plan_id_val:
                raise ValueError("Missing tenant_id or plan_id in checkout metadata")

            tenant_id = int(tenant_id_val)
            plan_id = int(plan_id_val)

            stripe_customer_id = (
                session.get("customer")
                if isinstance(session, dict)
                else getattr(session, "customer", None)
            )
            stripe_subscription_id = (
                session.get("subscription")
                if isinstance(session, dict)
                else getattr(session, "subscription", None)
            )

            self.tenant_repo.update_plan(tenant_id=tenant_id, plan_id=plan_id)
            self.subscription_repo.create_or_update(
                tenant_id=tenant_id,
                plan_id=plan_id,
                status="active",
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
            )

        elif event_type == "customer.subscription.updated":
            stripe_sub = (
                event["data"]["object"]
                if isinstance(event, dict)
                else event.data.object
            )
            sub_id = (
                stripe_sub.get("id")
                if isinstance(stripe_sub, dict)
                else getattr(stripe_sub, "id", None)
            )
            new_status = (
                stripe_sub.get("status")
                if isinstance(stripe_sub, dict)
                else getattr(stripe_sub, "status", None)
            )
            start_ts = (
                stripe_sub.get("current_period_start")
                if isinstance(stripe_sub, dict)
                else getattr(stripe_sub, "current_period_start", None)
            )
            end_ts = (
                stripe_sub.get("current_period_end")
                if isinstance(stripe_sub, dict)
                else getattr(stripe_sub, "current_period_end", None)
            )

            if sub_id:
                sub = self.subscription_repo.get_by_stripe_subscription_id(sub_id)
                if sub:
                    dt_start = (
                        datetime.fromtimestamp(start_ts, tz=timezone.utc).replace(tzinfo=None)
                        if start_ts
                        else None
                    )
                    dt_end = (
                        datetime.fromtimestamp(end_ts, tz=timezone.utc).replace(tzinfo=None)
                        if end_ts
                        else None
                    )
                    self.subscription_repo.create_or_update(
                        tenant_id=sub.tenant_id,
                        plan_id=sub.plan_id,
                        status=new_status or sub.status,
                        stripe_customer_id=sub.stripe_customer_id,
                        stripe_subscription_id=sub_id,
                        current_period_start=dt_start or sub.current_period_start,
                        current_period_end=dt_end or sub.current_period_end,
                    )
                    if new_status in ["canceled", "unpaid"]:
                        self.fallback_tenant_to_free(sub.tenant_id)

        elif event_type == "customer.subscription.deleted":
            stripe_sub = (
                event["data"]["object"]
                if isinstance(event, dict)
                else event.data.object
            )
            sub_id = (
                stripe_sub.get("id")
                if isinstance(stripe_sub, dict)
                else getattr(stripe_sub, "id", None)
            )

            if sub_id:
                sub = self.subscription_repo.get_by_stripe_subscription_id(sub_id)
                if sub:
                    self.subscription_repo.create_or_update(
                        tenant_id=sub.tenant_id,
                        plan_id=sub.plan_id,
                        status="canceled",
                        stripe_customer_id=sub.stripe_customer_id,
                        stripe_subscription_id=sub_id,
                    )
                    self.fallback_tenant_to_free(sub.tenant_id)

        # 3. Persist webhook event for replay protection
        self.webhook_event_repo.create(
            stripe_event_id=event_id,
            event_type=event_type,
        )

        # 4. Commit atomic transaction
        self.db.commit()

        return {
            "status": "success",
            "event_id": event_id,
            "event_type": event_type,
        }
