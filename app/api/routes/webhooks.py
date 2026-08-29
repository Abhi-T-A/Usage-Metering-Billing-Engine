from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
import stripe

from app.api.deps import get_webhook_service
from app.services.webhook_service import WebhookService

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


@router.post(
    "/stripe",
    status_code=status.HTTP_200_OK,
    summary="Stripe Webhook Handler",
    description="Receives raw Stripe webhook events, verifies cryptographic signatures, and updates subscription state idempotently.",
)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    webhook_service: WebhookService = Depends(get_webhook_service),
):
    if not stripe_signature or not stripe_signature.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required 'Stripe-Signature' header",
        )

    payload = await request.body()

    try:
        event = webhook_service.verify_and_construct_event(
            payload=payload,
            sig_header=stripe_signature.strip(),
        )
    except stripe.error.SignatureVerificationError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid Stripe signature",
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid webhook payload",
        )

    try:
        result = webhook_service.process_event(event)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    return result
