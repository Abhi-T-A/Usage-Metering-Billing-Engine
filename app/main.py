from fastapi import Depends, FastAPI

from app.api.routes import (
    billing_router,
    generate_router,
    usage_router,
    webhooks_router,
)
from app.core.auth import get_current_tenant
from app.models.tenant import Tenant

app = FastAPI(
    title="Usage Metering & Billing Engine",
    version="0.1.0",
)

app.include_router(generate_router)
app.include_router(billing_router)
app.include_router(webhooks_router)
app.include_router(usage_router)




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

