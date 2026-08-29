from pydantic import BaseModel, ConfigDict, Field


class CheckoutSessionRequest(BaseModel):
    plan_name: str = Field(
        description="Target subscription plan name (e.g. PRO)",
        min_length=1,
    )

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )


class CheckoutSessionResponse(BaseModel):
    checkout_url: str
    session_id: str
    plan_name: str

    model_config = ConfigDict(
        from_attributes=True,
    )
