from typing import Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.plan import Plan


class PlanRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, plan_id: int) -> Plan | None:
        return self.db.scalar(
            select(Plan).where(Plan.id == plan_id)
        )

    def get_by_name(self, name: str) -> Plan | None:
        return self.db.scalar(
            select(Plan).where(Plan.name == name)
        )

    def list_all(self) -> Sequence[Plan]:
        return self.db.scalars(
            select(Plan).order_by(Plan.id)
        ).all()
