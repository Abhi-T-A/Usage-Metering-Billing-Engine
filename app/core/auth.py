from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import verify_api_key
from app.models.tenant import Tenant


def get_current_tenant(
    x_api_key: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> Tenant:
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key",
        )

    tenants = db.scalars(select(Tenant)).all()

    for tenant in tenants:
        if verify_api_key(x_api_key, tenant.api_key_hash):
            return tenant

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
    )