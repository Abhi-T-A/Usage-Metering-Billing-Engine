from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.webhook_event import StripeWebhookEvent


class WebhookEventRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_event_id(self, stripe_event_id: str) -> StripeWebhookEvent | None:
        """Finds a previously processed webhook event by its Stripe event ID."""
        return self.db.scalar(
            select(StripeWebhookEvent).where(
                StripeWebhookEvent.stripe_event_id == stripe_event_id
            )
        )

    def create(self, stripe_event_id: str, event_type: str) -> StripeWebhookEvent:
        """Persists a new webhook event to guarantee deduplication across server restarts."""
        event = StripeWebhookEvent(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
        )
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event
