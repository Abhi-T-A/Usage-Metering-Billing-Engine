from datetime import datetime, timezone
import logging
import time
from typing import Any
import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.subscription import Subscription
from app.repositories.plan_repository import PlanRepository
from app.repositories.subscription_repository import SubscriptionRepository
from app.repositories.tenant_repository import TenantRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("SubscriptionReconciler")


class SubscriptionReconciler:
    def __init__(
        self,
        db: Session,
        plan_repo: PlanRepository,
        tenant_repo: TenantRepository,
        subscription_repo: SubscriptionRepository,
        stripe_secret_key: str | None = None,
        max_retries: int = 3,
        base_backoff_sec: float = 0.05,
    ) -> None:
        self.db = db
        self.plan_repo = plan_repo
        self.tenant_repo = tenant_repo
        self.subscription_repo = subscription_repo
        self.max_retries = max_retries
        self.base_backoff_sec = base_backoff_sec
        stripe.api_key = stripe_secret_key or settings.stripe_secret_key

    def alert_critical_failure(self, subscription_id: str, error: Exception) -> None:
        """Failure alert hook: triggered when retries are exhausted."""
        logger.critical(
            f"[CRITICAL_ALERT] Permanent reconciliation failure for subscription '{subscription_id}' after {self.max_retries} attempts: {error}"
        )

    def retrieve_stripe_subscription_with_retry(self, sub_id: str) -> Any:
        """Retrieves Stripe subscription with exponential backoff retries and failure alert."""
        for attempt in range(1, self.max_retries + 1):
            try:
                return stripe.Subscription.retrieve(sub_id)
            except stripe.error.InvalidRequestError:
                # Missing resource (404) should not be retried
                raise
            except stripe.error.StripeError as exc:
                if attempt < self.max_retries:
                    backoff = self.base_backoff_sec * (2 ** (attempt - 1))
                    logger.warning(
                        f"Transient Stripe error for {sub_id} on attempt {attempt}/{self.max_retries}: {exc}. Retrying in {backoff:.2f}s..."
                    )
                    time.sleep(backoff)
                else:
                    self.alert_critical_failure(sub_id, exc)
                    raise

    def reconcile_single(self, sub: Subscription) -> tuple[bool, str]:
        """Reconciles a single subscription with Stripe state.
        
        Returns: (was_updated: bool, message: str)
        """
        if not sub.stripe_subscription_id:
            return False, "No Stripe subscription ID"

        try:
            stripe_sub = self.retrieve_stripe_subscription_with_retry(
                sub.stripe_subscription_id
            )
        except stripe.error.InvalidRequestError:
            logger.warning(
                f"Subscription {sub.stripe_subscription_id} not found in Stripe. Marking as canceled."
            )
            sub.status = "canceled"
            self.fallback_tenant_to_free(sub.tenant_id)
            self.db.commit()
            return True, "Subscription missing in Stripe -> canceled"
        except stripe.error.StripeError as exc:
            logger.error(
                f"Stripe API error for subscription {sub.stripe_subscription_id}: {str(exc)}"
            )
            return False, f"Stripe API error: {str(exc)}"

        stripe_status = getattr(stripe_sub, "status", None) or stripe_sub["status"]
        period_start_ts = getattr(stripe_sub, "current_period_start", None) or stripe_sub.get("current_period_start")
        period_end_ts = getattr(stripe_sub, "current_period_end", None) or stripe_sub.get("current_period_end")

        updated = False

        if sub.status != stripe_status:
            logger.info(
                f"Status mismatch for tenant {sub.tenant_id}: local='{sub.status}', stripe='{stripe_status}'"
            )
            sub.status = stripe_status
            updated = True

            if stripe_status in ["canceled", "unpaid"]:
                self.fallback_tenant_to_free(sub.tenant_id)

        if period_start_ts:
            dt_start = datetime.fromtimestamp(period_start_ts, tz=timezone.utc).replace(tzinfo=None)
            if sub.current_period_start != dt_start:
                sub.current_period_start = dt_start
                updated = True

        if period_end_ts:
            dt_end = datetime.fromtimestamp(period_end_ts, tz=timezone.utc).replace(tzinfo=None)
            if sub.current_period_end != dt_end:
                sub.current_period_end = dt_end
                updated = True

        if updated:
            self.db.add(sub)
            self.db.commit()
            return True, f"Synchronized with Stripe status='{stripe_status}'"

        return False, "In sync"

    def fallback_tenant_to_free(self, tenant_id: int) -> None:
        """Falls back a tenant to the default FREE plan upon cancellation."""
        free_plan = self.plan_repo.get_by_name("FREE") or self.plan_repo.get_by_name("TEST_FREE")
        if free_plan:
            self.tenant_repo.update_plan(tenant_id, free_plan.id)
            logger.info(f"Tenant {tenant_id} downgraded to plan {free_plan.name}")

    def reconcile_all(self) -> dict[str, int]:
        """Reconciles all tracked subscriptions."""
        subscriptions = self.subscription_repo.list_tracked_subscriptions()
        logger.info(f"Starting reconciliation for {len(subscriptions)} subscriptions...")

        stats = {
            "total_checked": len(subscriptions),
            "updated": 0,
            "in_sync": 0,
            "errors": 0,
        }

        for sub in subscriptions:
            try:
                was_updated, msg = self.reconcile_single(sub)
                if was_updated:
                    stats["updated"] += 1
                elif "error" in msg.lower():
                    stats["errors"] += 1
                else:
                    stats["in_sync"] += 1
            except Exception as exc:
                logger.error(f"Unexpected error reconciling subscription {sub.id}: {exc}")
                stats["errors"] += 1

        logger.info(
            f"Reconciliation completed: {stats['updated']} updated, "
            f"{stats['in_sync']} in sync, {stats['errors']} errors."
        )
        return stats


def run_reconciliation() -> dict[str, int]:
    """Entry point for manual or scheduled cron execution."""
    db = SessionLocal()
    try:
        reconciler = SubscriptionReconciler(
            db=db,
            plan_repo=PlanRepository(db),
            tenant_repo=TenantRepository(db),
            subscription_repo=SubscriptionRepository(db),
        )
        return reconciler.reconcile_all()
    finally:
        db.close()


if __name__ == "__main__":
    run_reconciliation()
