from fastapi import Depends

from app.core.auth import get_current_tenant
from app.models.tenant import Tenant

from fastapi import FastAPI

app = FastAPI(
    title="Usage Metering & Billing Engine",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/protected")
def protected_route(
    tenant: Tenant = Depends(get_current_tenant),
):
    return {
        "tenant_id": tenant.id,
        "tenant_name": tenant.name,
    }
