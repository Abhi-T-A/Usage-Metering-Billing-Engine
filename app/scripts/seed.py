from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.plan import Plan


PLANS = [
    {
        "name": "FREE",
        "api_call_limit": 100,
        "ai_token_limit": 10_000,
        "price_cents": 0,
    },
    {
        "name": "PRO",
        "api_call_limit": 10_000,
        "ai_token_limit": 1_000_000,
        "price_cents": 2900,
    },
]


def seed_plans() -> None:
    db = SessionLocal()

    try:
        for plan_data in PLANS:
            existing_plan = db.scalar(
                select(Plan).where(
                    Plan.name == plan_data["name"]
                )
            )

            if existing_plan:
                print(f"Plan already exists: {plan_data['name']}")
                continue

            db.add(Plan(**plan_data))
            print(f"Created plan: {plan_data['name']}")

        db.commit()

    finally:
        db.close()


if __name__ == "__main__":
    seed_plans()