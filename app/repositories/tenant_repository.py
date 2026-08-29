from typing import Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.tenant import Tenant


class TenantRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, tenant_id: int, load_plan: bool = False) -> Tenant | None:
        query = select(Tenant).where(Tenant.id == tenant_id)
        if load_plan:
            query = query.options(joinedload(Tenant.plan))
        return self.db.scalar(query)

    def get_by_api_key_hash(self, api_key_hash: str, load_plan: bool = False) -> Tenant | None:
        query = select(Tenant).where(Tenant.api_key_hash == api_key_hash)
        if load_plan:
            query = query.options(joinedload(Tenant.plan))
        return self.db.scalar(query)

    def update_plan(self, tenant_id: int, plan_id: int) -> Tenant | None:
        tenant = self.get_by_id(tenant_id)
        if tenant:
            tenant.plan_id = plan_id
            self.db.add(tenant)
            self.db.flush()
            self.db.refresh(tenant)
        return tenant

    def list_all(self) -> Sequence[Tenant]:
        return self.db.scalars(
            select(Tenant).order_by(Tenant.id)
        ).all()
