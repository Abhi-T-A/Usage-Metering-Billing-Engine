from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field

from app.services.quota_service import UsageType


class UsageRecordRequest(BaseModel):
    type: str = Field(
        default=UsageType.API_CALL,
        description="Type of usage metric being recorded (e.g. API_CALL, AI_TOKENS)",
        min_length=1,
    )
    quantity: int = Field(
        default=1,
        gt=0,
        description="Quantity of usage to record. Must be strictly positive.",
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class UsageRecordResponse(BaseModel):
    id: int
    tenant_id: int
    type: str
    quantity: int
    idempotency_key: str
    created_at: datetime
    is_duplicate: bool = False

    model_config = ConfigDict(
        from_attributes=True,
    )
