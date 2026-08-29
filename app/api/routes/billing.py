from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_stripe_service
from app.core.auth import get_current_tenant
from app.models.tenant import Tenant
from app.schemas.billing import CheckoutSessionRequest, CheckoutSessionResponse
from app.services.stripe_service import (
    InvalidPlanSelectionError,
    PlanNotFoundError,
    StripeService,
)

router = APIRouter(prefix="/billing", tags=["Billing"])


@router.post(
    "/checkout",
    response_model=CheckoutSessionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Stripe Checkout Session",
    description="Initiates a Stripe Checkout session for subscription plan upgrades. Does not modify tenant plan directly.",
)
def create_checkout_session(
    payload: CheckoutSessionRequest,
    tenant: Tenant = Depends(get_current_tenant),
    stripe_service: StripeService = Depends(get_stripe_service),
):
    try:
        checkout_url, session_id = stripe_service.create_checkout_session(
            tenant=tenant,
            plan_name=payload.plan_name,
        )
    except PlanNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except InvalidPlanSelectionError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return CheckoutSessionResponse(
        checkout_url=checkout_url,
        session_id=session_id,
        plan_name=payload.plan_name.strip().upper(),
    )
