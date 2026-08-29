from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Tuple

from app.models.tenant import Tenant
from app.models.plan import Plan
from app.repositories.plan_repository import PlanRepository
from app.repositories.usage_repository import UsageRepository


class UsageType:
    API_CALL = "API_CALL"
    AI_TOKENS = "AI_TOKENS"
    INPUT_TOKENS = "INPUT_TOKENS"
    CACHED_INPUT_TOKENS = "CACHED_INPUT_TOKENS"
    OUTPUT_TOKENS = "OUTPUT_TOKENS"
    REASONING_TOKENS = "REASONING_TOKENS"

    TOKEN_TYPES = {
        AI_TOKENS,
        INPUT_TOKENS,
        CACHED_INPUT_TOKENS,
        OUTPUT_TOKENS,
        REASONING_TOKENS,
    }


class QuotaExceededError(Exception):
    """Domain exception raised when a tenant exceeds their plan quota."""

    def __init__(
        self,
        usage_type: str,
        current_usage: int,
        requested_quantity: int,
        limit: int,
    ) -> None:
        self.usage_type = usage_type
        self.current_usage = current_usage
        self.requested_quantity = requested_quantity
        self.limit = limit
        super().__init__(
            f"Quota exceeded for {usage_type}: current={current_usage}, "
            f"requested={requested_quantity}, limit={limit}"
        )


@dataclass(frozen=True)
class QuotaCheckResult:
    allowed: bool
    usage_type: str
    current_usage: int
    requested_quantity: int
    limit: int


class QuotaService:
    def __init__(
        self,
        usage_repo: UsageRepository,
        plan_repo: PlanRepository,
    ) -> None:
        self.usage_repo = usage_repo
        self.plan_repo = plan_repo

    @staticmethod
    def get_current_billing_period(
        reference_time: datetime | None = None,
    ) -> Tuple[datetime, datetime]:
        """Returns the start and end timestamps (UTC) for the current monthly billing period."""
        ref = reference_time or datetime.now(timezone.utc).replace(tzinfo=None)
        
        start_time = datetime(ref.year, ref.month, 1)
        
        if ref.month == 12:
            end_time = datetime(ref.year + 1, 1, 1)
        else:
            end_time = datetime(ref.year, ref.month + 1, 1)

        return start_time, end_time

    def get_tenant_plan(self, tenant: Tenant) -> Plan:
        """Resolves tenant plan using loaded relation or PlanRepository."""
        if tenant.plan:
            return tenant.plan
        
        plan = self.plan_repo.get_by_id(tenant.plan_id)
        if not plan:
            raise ValueError(f"Plan with id {tenant.plan_id} not found for tenant {tenant.id}")
        return plan

    def get_plan_limit(self, plan: Plan, usage_type: str) -> int:
        """Returns the numerical limit for a specific usage type from the plan."""
        if usage_type == UsageType.API_CALL:
            return plan.api_call_limit
        elif usage_type in UsageType.TOKEN_TYPES:
            return plan.ai_token_limit
        else:
            raise ValueError(f"Unsupported usage type: {usage_type}")

    def get_current_usage(
        self,
        tenant_id: int,
        usage_type: str,
        period: Tuple[datetime, datetime] | None = None,
    ) -> int:
        """Calculates total usage for a tenant within the current billing period."""
        if period is None:
            period = self.get_current_billing_period()

        start_time, end_time = period
        return self.usage_repo.get_usage_sum(
            tenant_id=tenant_id,
            type=usage_type,
            start_time=start_time,
            end_time=end_time,
        )

    def check_quota(
        self,
        tenant: Tenant,
        usage_type: str,
        requested_quantity: int = 1,
    ) -> QuotaCheckResult:
        """Checks if requested usage is allowed under tenant's current plan limits.
        
        Boundary rule:
        - Exactly reaching the limit (current + requested == limit) is ALLOWED.
        - Exceeding the limit (current + requested > limit) is REJECTED.
        """
        plan = self.get_tenant_plan(tenant)
        limit = self.get_plan_limit(plan, usage_type)
        current_usage = self.get_current_usage(tenant.id, usage_type)

        new_total = current_usage + requested_quantity
        allowed = new_total <= limit

        if not allowed:
            raise QuotaExceededError(
                usage_type=usage_type,
                current_usage=current_usage,
                requested_quantity=requested_quantity,
                limit=limit,
            )

        return QuotaCheckResult(
            allowed=True,
            usage_type=usage_type,
            current_usage=current_usage,
            requested_quantity=requested_quantity,
            limit=limit,
        )
