import hashlib
import hmac
import secrets
from typing import Any

from itsdangerous import BadSignature, BadTimeSignature, URLSafeTimedSerializer

from app.core.config import settings

PASSWORD_ITERATIONS = 120_000
TOKEN_SALT = "mobile-auth-token"


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        salt.encode("utf-8"),
        PASSWORD_ITERATIONS,
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${derived.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash:
        return False
    try:
        algorithm, iterations_raw, salt, digest = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        iterations = int(iterations_raw)
    except Exception:
        return False

    calculated = hashlib.pbkdf2_hmac(
        "sha256",
        (password or "").encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    ).hex()
    return hmac.compare_digest(calculated, digest)


def issue_mobile_token(payload: dict[str, Any]) -> str:
    serializer = URLSafeTimedSerializer(settings.mobile_auth_secret)
    return serializer.dumps(payload, salt=TOKEN_SALT)


def load_mobile_token(token: str) -> dict[str, Any] | None:
    serializer = URLSafeTimedSerializer(settings.mobile_auth_secret)
    try:
        payload = serializer.loads(
            token,
            salt=TOKEN_SALT,
            max_age=settings.mobile_auth_max_age_seconds,
        )
    except (BadSignature, BadTimeSignature):
        return None
    if isinstance(payload, dict):
        return payload
    return None
