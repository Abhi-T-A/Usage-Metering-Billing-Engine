from typing import Any
import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
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
        webhook_secret: str | None = None,
    ) -> None:
        self.db = db
        self.webhook_event_repo = webhook_event_repo
        self.tenant_repo = tenant_repo
        self.subscription_repo = subscription_repo
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

    def process_event(self, event: Any) -> dict[str, Any]:
        """Atomically processes a verified Stripe webhook event with deduplication.
        
        1. Checks if stripe_event_id has already been processed (replay protection).
        2. Dispatches event type (e.g. checkout.session.completed).
        3. Persists event ID in stripe_webhook_events and commits the transaction.
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

        # 2. Handle checkout.session.completed
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

            # Update tenant plan
            self.tenant_repo.update_plan(tenant_id=tenant_id, plan_id=plan_id)

            # Create or update subscription record
            self.subscription_repo.create_or_update(
                tenant_id=tenant_id,
                plan_id=plan_id,
                status="active",
                stripe_customer_id=stripe_customer_id,
                stripe_subscription_id=stripe_subscription_id,
            )

        # 3. Persist webhook event for persistent deduplication
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
