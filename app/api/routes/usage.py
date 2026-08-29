from fastapi import APIRouter, Depends, status

from app.api.deps import get_usage_rollup_service
from app.core.auth import get_current_tenant
from app.models.tenant import Tenant
from app.schemas.rollup import CostSummary, MetricUsage, UsageRollupResponse
from app.services.rollup_service import UsageRollupService

router = APIRouter(prefix="/usage", tags=["Usage Rollup"])


@router.get(
    "",
    response_model=UsageRollupResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current Monthly Usage Summary",
    description="Rolls up month-to-date API calls and token metrics with remaining quotas and estimated costs.",
)
def get_monthly_usage_summary(
    tenant: Tenant = Depends(get_current_tenant),
    rollup_service: UsageRollupService = Depends(get_usage_rollup_service),
):
    summary = rollup_service.get_monthly_usage(tenant=tenant)

    return UsageRollupResponse(
        tenant_id=summary.tenant_id,
        tenant_name=summary.tenant_name,
        plan_name=summary.plan_name,
        period_start=summary.period_start,
        period_end=summary.period_end,
        api_calls=MetricUsage(
            used=summary.api_calls.used,
            limit=summary.api_calls.limit,
            remaining=summary.api_calls.remaining,
        ),
        ai_tokens=MetricUsage(
            used=summary.ai_tokens.used,
            limit=summary.ai_tokens.limit,
            remaining=summary.ai_tokens.remaining,
        ),
        cost=CostSummary(
            total_cost_microcents=summary.cost.total_cost_microcents,
            total_cost_cents=summary.cost.total_cost_cents,
        ),
    )
