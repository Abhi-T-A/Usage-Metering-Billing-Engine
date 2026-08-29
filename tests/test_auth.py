from fastapi.testclient import TestClient


def test_protected_route_with_valid_api_key(
    client: TestClient,
    test_tenant_data: dict,
):
    """Accessing /protected with a valid tenant API key returns tenant metadata."""
    response = client.get(
        "/protected",
        headers=test_tenant_data["headers"],
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tenant_id"] == test_tenant_data["tenant"].id
    assert data["tenant_name"] == "Acme Corp Test Tenant"


def test_protected_route_with_missing_api_key(client: TestClient):
    """Accessing /protected without an API key returns 401."""
    response = client.get("/protected")
    assert response.status_code == 401
    assert response.json()["detail"] == "Missing API key"


def test_protected_route_with_invalid_api_key(client: TestClient):
    """Accessing /protected with an unknown API key returns 401."""
    response = client.get(
        "/protected",
        headers={"X-API-Key": "completely-fake-api-key"},
    )
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid API key"
