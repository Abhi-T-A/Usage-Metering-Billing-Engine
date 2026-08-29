import stripe
from app.core.config import settings
from app.models.tenant import Tenant
from app.repositories.plan_repository import PlanRepository


class PlanNotFoundError(Exception):
    """Raised when a requested plan does not exist."""
    pass


class InvalidPlanSelectionError(Exception):
    """Raised when a tenant requests an invalid or redundant plan change."""
    pass


class StripeService:
    def __init__(
        self,
        plan_repo: PlanRepository,
        stripe_secret_key: str | None = None,
    ) -> None:
        self.plan_repo = plan_repo
        self.stripe_secret_key = stripe_secret_key or settings.stripe_secret_key
        stripe.api_key = self.stripe_secret_key

    def create_checkout_session(
        self,
        tenant: Tenant,
        plan_name: str,
        success_url: str | None = None,
        cancel_url: str | None = None,
    ) -> tuple[str, str]:
        """Creates a Stripe Checkout Session in subscription mode.
        
        Guarantees:
        - Target plan must exist in database.
        - Tenant cannot checkout for the plan they already occupy.
        - Target plan must be a paid plan (> 0 cents).
        - Tenant plan is NOT modified at this stage (awaiting verified webhook).
        """
        normalized_name = plan_name.strip().upper()
        target_plan = self.plan_repo.get_by_name(normalized_name)

        if not target_plan:
            raise PlanNotFoundError(f"Plan '{plan_name}' not found")

        if tenant.plan_id == target_plan.id:
            raise InvalidPlanSelectionError(
                f"Tenant is already subscribed to the '{target_plan.name}' plan"
            )

        if target_plan.price_cents <= 0:
            raise InvalidPlanSelectionError(
                f"Cannot initiate paid checkout for free plan '{target_plan.name}'"
            )

        base_success_url = (
            success_url
            or "http://localhost:8000/billing/success?session_id={CHECKOUT_SESSION_ID}"
        )
        base_cancel_url = cancel_url or "http://localhost:8000/billing/cancel"

        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[
                {
                    "price_data": {
                        "currency": "usd",
                        "unit_amount": target_plan.price_cents,
                        "recurring": {
                            "interval": "month",
                        },
                        "product_data": {
                            "name": f"{target_plan.name} Subscription Plan",
                        },
                    },
                    "quantity": 1,
                }
            ],
            metadata={
                "tenant_id": str(tenant.id),
                "plan_id": str(target_plan.id),
                "plan_name": target_plan.name,
            },
            success_url=base_success_url,
            cancel_url=base_cancel_url,
        )

        return session.url, session.id
