from app.core.config import settings

_SCOPE_SEPARATOR = "::"
_LEGACY_VARIANTS = {"", "default", "internal"}


def normalize_client_variant(value: str | None) -> str:
    normalized = (value or "").strip().lower()
    if normalized in _LEGACY_VARIANTS:
        return settings.internal_auth_variant
    return normalized or settings.internal_auth_variant


def build_scoped_username(username: str, variant: str | None = None) -> str:
    normalized_username = (username or "").strip()
    if _SCOPE_SEPARATOR in normalized_username:
        return normalized_username
    return f"{normalize_client_variant(variant)}{_SCOPE_SEPARATOR}{normalized_username}"


def build_scoped_device_id(device_id: str, variant: str | None = None) -> str:
    normalized_device_id = (device_id or "").strip()
    if _SCOPE_SEPARATOR in normalized_device_id:
        return normalized_device_id
    return f"{normalize_client_variant(variant)}{_SCOPE_SEPARATOR}{normalized_device_id}"


def extract_raw_scoped_value(value: str | None) -> str:
    normalized = (value or "").strip()
    if _SCOPE_SEPARATOR not in normalized:
        return normalized
    return normalized.split(_SCOPE_SEPARATOR, 1)[1].strip()


def extract_scoped_variant(value: str | None) -> str:
    normalized = (value or "").strip()
    if _SCOPE_SEPARATOR not in normalized:
        return ""
    return normalized.split(_SCOPE_SEPARATOR, 1)[0].strip().lower()
