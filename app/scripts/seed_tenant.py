from secrets import token_urlsafe

from sqlalchemy import select

from app.core.database import SessionLocal
from app.core.security import hash_api_key
from app.models.plan import Plan
from app.models.tenant import Tenant


TENANT_NAME = "Demo Tenant"


def seed_tenant() -> None:
    db = SessionLocal()

    try:
        existing_tenant = db.scalar(
            select(Tenant).where(
                Tenant.name == TENANT_NAME
            )
        )

        if existing_tenant:
            print(f"Tenant already exists: {existing_tenant.name}")
            return

        free_plan = db.scalar(
            select(Plan).where(
                Plan.name == "FREE"
            )
        )

        if not free_plan:
            raise RuntimeError(
                "FREE plan not found. Run the plan seed first."
            )

        api_key = token_urlsafe(32)

        tenant = Tenant(
            name=TENANT_NAME,
            plan_id=free_plan.id,
            api_key_hash=hash_api_key(api_key),
        )

        db.add(tenant)
        db.commit()
        db.refresh(tenant)

        print(f"Created tenant: {tenant.name}")
        print(f"Tenant ID: {tenant.id}")
        print(f"API Key: {api_key}")

    finally:
        db.close()


if __name__ == "__main__":
    seed_tenant()