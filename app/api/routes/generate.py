from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import JSONResponse

from app.api.deps import get_metering_service
from app.core.auth import get_current_tenant
from app.models.tenant import Tenant
from app.schemas.usage import UsageRecordRequest, UsageRecordResponse
from app.services.metering_service import MeteringService
from app.services.quota_service import QuotaExceededError

router = APIRouter(tags=["Metering"])


@router.post(
    "/generate",
    response_model=UsageRecordResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record billable usage",
    description="Idempotently meters API calls / tokens after enforcing tenant subscription quotas.",
)
def record_generate_usage(
    payload: UsageRecordRequest,
    response: Response,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    tenant: Tenant = Depends(get_current_tenant),
    metering_service: MeteringService = Depends(get_metering_service),
):
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'Idempotency-Key' header",
        )

    try:
        result = metering_service.record_usage(
            tenant=tenant,
            usage_type=payload.type,
            quantity=payload.quantity,
            idempotency_key=idempotency_key.strip(),
        )
    except QuotaExceededError as exc:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": f"Monthly quota exceeded for {exc.usage_type}",
                "usage_type": exc.usage_type,
                "current_usage": exc.current_usage,
                "requested_quantity": exc.requested_quantity,
                "limit": exc.limit,
            },
        )

    if result.is_duplicate:
        response.status_code = status.HTTP_200_OK

    return UsageRecordResponse(
        id=result.usage_event.id,
        tenant_id=result.usage_event.tenant_id,
        type=result.usage_event.type,
        quantity=result.usage_event.quantity,
        idempotency_key=result.usage_event.idempotency_key,
        created_at=result.usage_event.created_at,
        is_duplicate=result.is_duplicate,
    )
