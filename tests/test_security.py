from app.core.security import hash_api_key, verify_api_key


def test_api_key_hashing():
    api_key = "test-api-key-123"

    hashed = hash_api_key(api_key)

    assert hashed != api_key
    assert verify_api_key(api_key, hashed)
    assert not verify_api_key("wrong-key", hashed)