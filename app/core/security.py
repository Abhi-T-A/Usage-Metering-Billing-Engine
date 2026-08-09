from pwdlib import PasswordHash


password_hash = PasswordHash.recommended()


def hash_api_key(api_key: str) -> str:
    return password_hash.hash(api_key)


def verify_api_key(api_key: str, hashed_api_key: str) -> bool:
    return password_hash.verify(api_key, hashed_api_key)