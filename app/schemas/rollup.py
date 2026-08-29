from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class MetricUsage(BaseModel):
    used: int = Field(description="Total quantity consumed in current period")
    limit: int = Field(description="Plan allowance for this metric")
    remaining: int = Field(description="Remaining quota (never negative)")

    model_config = ConfigDict(from_attributes=True)


class CostSummary(BaseModel):
    total_cost_microcents: int = Field(description="Exact total cost in micro-cents")
    total_cost_cents: int = Field(description="Total cost rounded up to integer cents")

    model_config = ConfigDict(from_attributes=True)


class UsageRollupResponse(BaseModel):
    tenant_id: int
    tenant_name: str
    plan_name: str
    period_start: datetime
    period_end: datetime
    api_calls: MetricUsage
    ai_tokens: MetricUsage
    cost: CostSummary

    model_config = ConfigDict(from_attributes=True)
