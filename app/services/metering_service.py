from dataclasses import dataclass
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.usage_event import UsageEvent
from app.repositories.usage_repository import UsageRepository
from app.services.quota_service import QuotaCheckResult, QuotaService


@dataclass(frozen=True)
class MeteringResult:
    usage_event: UsageEvent
    is_duplicate: bool
    quota_check: QuotaCheckResult | None


class MeteringService:
    def __init__(
        self,
        db: Session,
        usage_repo: UsageRepository,
        quota_service: QuotaService,
    ) -> None:
        self.db = db
        self.usage_repo = usage_repo
        self.quota_service = quota_service

    def record_usage(
        self,
        tenant: Tenant,
        usage_type: str,
        quantity: int,
        idempotency_key: str,
    ) -> MeteringResult:
        """Records a billable usage event idempotently with quota enforcement.
        
        1. Check idempotency: If an event exists for (tenant.id, idempotency_key), return it.
        2. Check quota: If not duplicate, verify current + quantity <= plan limit.
        3. Persist: Create and commit the new UsageEvent.
        """
        # Step 1: Idempotency Check
        existing_event = self.usage_repo.get_by_idempotency_key(
            tenant_id=tenant.id,
            idempotency_key=idempotency_key,
        )
        if existing_event is not None:
            return MeteringResult(
                usage_event=existing_event,
                is_duplicate=True,
                quota_check=None,
            )

        # Step 2: Quota Check (raises QuotaExceededError if over limit)
        quota_result = self.quota_service.check_quota(
            tenant=tenant,
            usage_type=usage_type,
            requested_quantity=quantity,
        )

        # Step 3: Persistence within transaction
        event = self.usage_repo.create(
            tenant_id=tenant.id,
            type=usage_type,
            quantity=quantity,
            idempotency_key=idempotency_key,
        )
        self.db.commit()
        self.db.refresh(event)

        return MeteringResult(
            usage_event=event,
            is_duplicate=False,
            quota_check=quota_result,
        )
