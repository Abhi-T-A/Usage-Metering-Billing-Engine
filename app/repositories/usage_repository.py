from datetime import datetime
from typing import Sequence
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.usage_event import UsageEvent


class UsageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_idempotency_key(
        self,
        tenant_id: int,
        idempotency_key: str,
    ) -> UsageEvent | None:
        """Find an existing usage event for a specific tenant and idempotency key.
        
        Guarantees tenant isolation by filtering on both tenant_id and idempotency_key.
        """
        return self.db.scalar(
            select(UsageEvent).where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.idempotency_key == idempotency_key,
            )
        )

    def create(
        self,
        tenant_id: int,
        type: str,
        quantity: int,
        idempotency_key: str,
    ) -> UsageEvent:
        """Create and persist a new usage event."""
        event = UsageEvent(
            tenant_id=tenant_id,
            type=type,
            quantity=quantity,
            idempotency_key=idempotency_key,
        )
        self.db.add(event)
        self.db.flush()
        self.db.refresh(event)
        return event

    def get_usage_sum(
        self,
        tenant_id: int,
        type: str,
        start_time: datetime,
        end_time: datetime,
    ) -> int:
        """Aggregate total quantity used by a tenant for a specific usage type within a time window."""
        result = self.db.scalar(
            select(func.coalesce(func.sum(UsageEvent.quantity), 0)).where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.type == type,
                UsageEvent.created_at >= start_time,
                UsageEvent.created_at < end_time,
            )
        )
        return int(result or 0)

    def list_by_tenant_and_period(
        self,
        tenant_id: int,
        start_time: datetime,
        end_time: datetime,
    ) -> Sequence[UsageEvent]:
        """Fetch all usage events for a tenant in a given period."""
        return self.db.scalars(
            select(UsageEvent)
            .where(
                UsageEvent.tenant_id == tenant_id,
                UsageEvent.created_at >= start_time,
                UsageEvent.created_at < end_time,
            )
            .order_by(UsageEvent.created_at.asc())
        ).all()
