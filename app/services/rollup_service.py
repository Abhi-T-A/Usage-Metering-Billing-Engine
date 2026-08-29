from dataclasses import dataclass
from datetime import datetime

from app.models.tenant import Tenant
from app.repositories.usage_repository import UsageRepository
from app.services.pricing_service import (
    PricingResult,
    PricingService,
    TokenUsageBreakdown,
)
from app.services.quota_service import QuotaService, UsageType


@dataclass(frozen=True)
class MetricSummary:
    used: int
    limit: int
    remaining: int


@dataclass(frozen=True)
class MonthlyUsageSummary:
    tenant_id: int
    tenant_name: str
    plan_name: str
    period_start: datetime
    period_end: datetime
    api_calls: MetricSummary
    ai_tokens: MetricSummary
    cost: PricingResult


class UsageRollupService:
    def __init__(
        self,
        usage_repo: UsageRepository,
        quota_service: QuotaService,
        pricing_service: PricingService,
    ) -> None:
        self.usage_repo = usage_repo
        self.quota_service = quota_service
        self.pricing_service = pricing_service

    def get_monthly_usage(self, tenant: Tenant) -> MonthlyUsageSummary:
        """Aggregates monthly usage and calculates pricing costs for an authenticated tenant."""
        period_start, period_end = self.quota_service.get_current_billing_period()
        plan = self.quota_service.get_tenant_plan(tenant)

        # Retrieve all usage events for the tenant in the current billing period
        events = self.usage_repo.list_by_tenant_and_period(
            tenant_id=tenant.id,
            start_time=period_start,
            end_time=period_end,
        )

        api_calls_used = 0
        input_tokens = 0
        cached_input_tokens = 0
        output_tokens = 0
        reasoning_tokens = 0
        general_tokens = 0

        for event in events:
            if event.type == UsageType.API_CALL:
                api_calls_used += event.quantity
            elif event.type == UsageType.INPUT_TOKENS:
                input_tokens += event.quantity
            elif event.type == UsageType.CACHED_INPUT_TOKENS:
                cached_input_tokens += event.quantity
            elif event.type == UsageType.OUTPUT_TOKENS:
                output_tokens += event.quantity
            elif event.type == UsageType.REASONING_TOKENS:
                reasoning_tokens += event.quantity
            elif event.type == UsageType.AI_TOKENS:
                general_tokens += event.quantity

        total_ai_tokens_used = (
            input_tokens
            + cached_input_tokens
            + output_tokens
            + reasoning_tokens
            + general_tokens
        )

        # Calculate remaining quota (guaranteed never negative)
        api_calls_remaining = max(0, plan.api_call_limit - api_calls_used)
        ai_tokens_remaining = max(0, plan.ai_token_limit - total_ai_tokens_used)

        # Calculate exact monetary cost
        token_breakdown = TokenUsageBreakdown(
            input_tokens=input_tokens + general_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
        )
        cost_result = self.pricing_service.calculate_cost(
            tokens=token_breakdown,
            api_calls=api_calls_used,
        )

        return MonthlyUsageSummary(
            tenant_id=tenant.id,
            tenant_name=tenant.name,
            plan_name=plan.name,
            period_start=period_start,
            period_end=period_end,
            api_calls=MetricSummary(
                used=api_calls_used,
                limit=plan.api_call_limit,
                remaining=api_calls_remaining,
            ),
            ai_tokens=MetricSummary(
                used=total_ai_tokens_used,
                limit=plan.ai_token_limit,
                remaining=ai_tokens_remaining,
            ),
            cost=cost_result,
        )
