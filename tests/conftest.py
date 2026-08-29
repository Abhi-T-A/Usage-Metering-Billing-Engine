import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.core.security import hash_api_key
from app.main import app
from app.models.plan import Plan
from app.models.tenant import Tenant

# In-memory SQLite for deterministic, isolated automated tests
TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    """Create all schema tables before each test and drop them after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db_session():
    """Provide an isolated database session for direct test assertions."""
    session: Session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db_session: Session):
    """FastAPI TestClient with overridden database dependency."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_plan(db_session: Session) -> Plan:
    """Fixture providing a standard test plan with 10 API calls and 1,000 AI tokens limit."""
    plan = Plan(
        name="TEST_FREE",
        api_call_limit=10,
        ai_token_limit=1000,
        price_cents=0,
    )
    db_session.add(plan)
    db_session.commit()
    db_session.refresh(plan)
    return plan


@pytest.fixture
def test_tenant_data(db_session: Session, test_plan: Plan):
    """Fixture providing an active test tenant and raw API key."""
    raw_api_key = "test-secret-key-probe"
    tenant = Tenant(
        name="Acme Corp Test Tenant",
        plan_id=test_plan.id,
        api_key_hash=hash_api_key(raw_api_key),
    )
    db_session.add(tenant)
    db_session.commit()
    db_session.refresh(tenant)
    return {
        "tenant": tenant,
        "plan": test_plan,
        "api_key": raw_api_key,
        "headers": {"X-API-Key": raw_api_key},
    }
