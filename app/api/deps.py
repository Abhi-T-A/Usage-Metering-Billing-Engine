from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.tenant_repository import TenantRepository
from app.repositories.usage_repository import UsageRepository
from app.repositories.webhook_event_repository import WebhookEventRepository
from app.services.metering_service import MeteringService
from app.services.pricing_service import PricingService
from app.services.quota_service import QuotaService
from app.services.rollup_service import UsageRollupService
from app.services.stripe_service import StripeService
from app.services.webhook_service import WebhookService


def get_usage_repository(db: Session = Depends(get_db)) -> UsageRepository:
    return UsageRepository(db)


def get_plan_repository(db: Session = Depends(get_db)) -> PlanRepository:
    return PlanRepository(db)


def get_tenant_repository(db: Session = Depends(get_db)) -> TenantRepository:
    return TenantRepository(db)


def get_subscription_repository(db: Session = Depends(get_db)) -> SubscriptionRepository:
    return SubscriptionRepository(db)


def get_webhook_event_repository(db: Session = Depends(get_db)) -> WebhookEventRepository:
    return WebhookEventRepository(db)


def get_quota_service(
    usage_repo: UsageRepository = Depends(get_usage_repository),
    plan_repo: PlanRepository = Depends(get_plan_repository),
) -> QuotaService:
    return QuotaService(usage_repo=usage_repo, plan_repo=plan_repo)


def get_metering_service(
    db: Session = Depends(get_db),
    usage_repo: UsageRepository = Depends(get_usage_repository),
    quota_service: QuotaService = Depends(get_quota_service),
) -> MeteringService:
    return MeteringService(
        db=db,
        usage_repo=usage_repo,
        quota_service=quota_service,
    )


def get_pricing_service() -> PricingService:
    return PricingService()


def get_stripe_service(
    plan_repo: PlanRepository = Depends(get_plan_repository),
) -> StripeService:
    return StripeService(plan_repo=plan_repo)


def get_webhook_service(
    db: Session = Depends(get_db),
    webhook_event_repo: WebhookEventRepository = Depends(get_webhook_event_repository),
    tenant_repo: TenantRepository = Depends(get_tenant_repository),
    subscription_repo: SubscriptionRepository = Depends(get_subscription_repository),
    plan_repo: PlanRepository = Depends(get_plan_repository),
) -> WebhookService:
    return WebhookService(
        db=db,
        webhook_event_repo=webhook_event_repo,
        tenant_repo=tenant_repo,
        subscription_repo=subscription_repo,
        plan_repo=plan_repo,
    )


def get_usage_rollup_service(
    usage_repo: UsageRepository = Depends(get_usage_repository),
    quota_service: QuotaService = Depends(get_quota_service),
    pricing_service: PricingService = Depends(get_pricing_service),
) -> UsageRollupService:
    return UsageRollupService(
        usage_repo=usage_repo,
        quota_service=quota_service,
        pricing_service=pricing_service,
    )
