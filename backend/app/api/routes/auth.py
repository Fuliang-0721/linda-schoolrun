from fastapi import APIRouter, Depends, Query, Request

from app.api.dependencies import get_mobile_auth_service, require_current_account
from app.application.schemas.auth_schemas import (
    AccountResponse,
    AuthAlertListResponse,
    AuthLoginRequest,
    AuthLoginResponse,
    AuthMeResponse,
)
from app.application.services.mobile_auth_service import MobileAuthService

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=AuthLoginResponse)
def login(
    request: Request,
    payload: AuthLoginRequest,
    auth_service: MobileAuthService = Depends(get_mobile_auth_service),
) -> AuthLoginResponse:
    return auth_service.login(payload, _get_request_ip(request))


@router.get("/me", response_model=AuthMeResponse)
def me(account: AccountResponse = Depends(require_current_account)) -> AuthMeResponse:
    return AuthMeResponse(authenticated=True, account=account)


@router.get("/alerts", response_model=AuthAlertListResponse)
def alerts(
    mark_read: bool = Query(default=True, alias="markRead"),
    account: AccountResponse = Depends(require_current_account),
    auth_service: MobileAuthService = Depends(get_mobile_auth_service),
) -> AuthAlertListResponse:
    return auth_service.get_unread_alerts(account.id, mark_read)


def _get_request_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
