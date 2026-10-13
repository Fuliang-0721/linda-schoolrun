from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.application.schemas.auth_schemas import AccountResponse
from app.application.services.mobile_auth_service import MobileAuthService
from app.application.services.shared_nfc_service import SharedNfcService
from app.application.services.shared_route_service import SharedRouteService
from app.core.security import load_mobile_token
from app.infrastructure.db.session import get_db_session
from app.infrastructure.repositories.shared_nfc_sql_repository import SharedNfcSqlRepository
from app.infrastructure.repositories.shared_route_sql_repository import SharedRouteSqlRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_db(db: Session = Depends(get_db_session)) -> Session:
    return db


@dataclass
class ClientContext:
    variant: str
    account: AccountResponse | None = None


def get_route_service(db: Session = Depends(get_db_session)) -> SharedRouteService:
    return SharedRouteService(SharedRouteSqlRepository(db))


def get_nfc_service(db: Session = Depends(get_db_session)) -> SharedNfcService:
    return SharedNfcService(SharedNfcSqlRepository(db))


def get_mobile_auth_service(db: Session = Depends(get_db_session)) -> MobileAuthService:
    return MobileAuthService(db)


def get_client_context(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: MobileAuthService = Depends(get_mobile_auth_service),
    variant_header: str | None = Header(default=None, alias="X-Client-Variant"),
) -> ClientContext:
    normalized_variant = (variant_header or "public").strip().lower()
    account = None

    if credentials is not None and credentials.scheme.lower() == "bearer":
        payload = load_mobile_token(credentials.credentials)
        if payload is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录。")
        token_variant = str(payload.get("variant", ""))
        auth_service.ensure_device_request_allowed(str(payload.get("deviceId", "")), token_variant)
        account = auth_service.require_active_account(str(payload.get("accountId", "")), token_variant)

    if normalized_variant == "exclusive" and account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录版接口需要先完成登录。")

    if normalized_variant not in {"public", "exclusive"}:
        normalized_variant = "public"

    return ClientContext(variant=normalized_variant, account=account)


def get_optional_account(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_service: MobileAuthService = Depends(get_mobile_auth_service),
    _variant_header: str | None = Header(default=None, alias="X-Client-Variant"),
) -> AccountResponse | None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        return None
    payload = load_mobile_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录。")
    variant = str(payload.get("variant", ""))
    auth_service.ensure_device_request_allowed(str(payload.get("deviceId", "")), variant)
    return auth_service.require_active_account(str(payload.get("accountId", "")), variant)


def require_current_account(
    account: AccountResponse | None = Depends(get_optional_account),
) -> AccountResponse:
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="缺少登录凭证。")
    return account


def get_release_identity(account=Depends(get_optional_account)):
    from app.core.config import settings
    if account is None or account.clientVariant != settings.internal_auth_variant:
        return ("stable", "")
    return ("internal", account.boundDeviceId)
