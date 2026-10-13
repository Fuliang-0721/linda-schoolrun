from fastapi import APIRouter, File, Request, UploadFile, status
from fastapi.responses import JSONResponse

from app.application.schemas.admin_schemas import (
    ActionMessageResponse,
    AdminLoginRequest,
    AdminSessionResponse,
)
from app.application.schemas.app_log_schemas import (
    InternalSoftwareNameEnvelope,
    InternalSoftwareNameListEnvelope,
    SubmitInternalSoftwareNameRequest,
)
from app.application.schemas.auth_schemas import (
    AuthDeviceEnvelope,
    AuthDeviceListEnvelope,
    UpdateAuthDeviceRequest,
)
from app.application.schemas.internal_account_schemas import (
    BanInternalAccountRequest,
    CreateInternalAccountRequest,
    InternalAccountEnvelope,
    InternalAccountListEnvelope,
    UpdateInternalAccountRequest,
)
from app.application.schemas.nfc_schemas import (
    CreateSharedNfcRequest,
    SharedNfcEnvelope,
    SharedNfcListEnvelope,
)
from app.application.schemas.notice_schemas import (
    AppNoticeEnvelope,
    UpdateAppNoticeRequest,
)
from app.application.schemas.route_schemas import (
    CreateSharedRouteRequest,
    SharedRouteAdminListEnvelope,
    SharedRouteDetailEnvelope,
)
from app.application.schemas.tip_schemas import (
    AdminSaveUsageTipRequest,
    TipImportWordResponse,
    UsageTipEnvelope,
    UsageTipListEnvelope,
)
from app.application.services.admin_auth_service import AdminAuthService
from app.application.services.admin_device_service import AdminDeviceService
from app.application.services.admin_nfc_service import AdminNfcService
from app.application.services.admin_route_service import AdminRouteService
from app.application.services.admin_usage_tip_service import AdminUsageTipService
from app.application.services.app_log_service import AppLogService
from app.application.services.app_notice_service import AppNoticeService
from app.application.services.internal_account_admin_service import InternalAccountAdminService
from app.core.exceptions import ResourceNotFoundError
from app.web.auth import ADMIN_SESSION_KEY, require_admin_session

router = APIRouter(prefix="/admin")
LOGIN_FSR_CLIENT_VARIANT = "exclusive"


@router.post("/login", response_model=AdminSessionResponse)
def admin_login(request: Request, payload: AdminLoginRequest):
    auth_service = AdminAuthService()
    if not auth_service.verify_credentials(payload.username, payload.password):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "账号或密码错误"},
        )

    request.session[ADMIN_SESSION_KEY] = payload.username
    return AdminSessionResponse(authenticated=True, username=payload.username)


@router.post("/logout", response_model=ActionMessageResponse)
def admin_logout(request: Request):
    request.session.clear()
    return ActionMessageResponse(message="已退出登录")


@router.get("/me", response_model=AdminSessionResponse)
def admin_me(request: Request):
    username = request.session.get(ADMIN_SESSION_KEY)
    return AdminSessionResponse(authenticated=bool(username), username=username)


@router.get("/notice", response_model=AppNoticeEnvelope)
def admin_get_notice(request: Request):
    require_admin_session(request)
    return AppNoticeEnvelope(data=AppNoticeService(request.state.db).get_notice())


@router.put("/notice", response_model=AppNoticeEnvelope)
def admin_update_notice(payload: UpdateAppNoticeRequest, request: Request):
    require_admin_session(request)
    return AppNoticeEnvelope(data=AppNoticeService(request.state.db).update_notice(payload))


@router.get("/internal-software-names", response_model=InternalSoftwareNameListEnvelope)
def admin_list_internal_software_names(request: Request):
    require_admin_session(request)
    return InternalSoftwareNameListEnvelope(items=AppLogService(request.state.db).list_admin_software_names())


@router.post(
    "/internal-software-names",
    response_model=InternalSoftwareNameEnvelope,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_internal_software_name(payload: SubmitInternalSoftwareNameRequest, request: Request):
    require_admin_session(request)
    return InternalSoftwareNameEnvelope(data=AppLogService(request.state.db).create_approved_software_name(payload))


@router.post("/internal-software-names/{name_id}/approve", response_model=InternalSoftwareNameEnvelope)
def admin_approve_internal_software_name(name_id: str, request: Request):
    require_admin_session(request)
    return InternalSoftwareNameEnvelope(data=AppLogService(request.state.db).approve_software_name(name_id))


@router.post("/internal-software-names/{name_id}/reject", response_model=InternalSoftwareNameEnvelope)
def admin_reject_internal_software_name(name_id: str, request: Request):
    require_admin_session(request)
    return InternalSoftwareNameEnvelope(data=AppLogService(request.state.db).reject_software_name(name_id))


@router.delete("/internal-software-names/{name_id}", response_model=ActionMessageResponse)
def admin_delete_internal_software_name(name_id: str, request: Request):
    require_admin_session(request)
    AppLogService(request.state.db).delete_software_name(name_id)
    return ActionMessageResponse(message="内部软件名已删除")


@router.get("/accounts", response_model=InternalAccountListEnvelope)
def admin_list_accounts(request: Request, clientVariant: str = LOGIN_FSR_CLIENT_VARIANT):
    require_admin_session(request)
    return InternalAccountListEnvelope(
        items=InternalAccountAdminService(request.state.db, clientVariant).list_accounts()
    )


@router.post("/accounts", response_model=InternalAccountEnvelope, status_code=status.HTTP_201_CREATED)
def admin_create_account(
    payload: CreateInternalAccountRequest,
    request: Request,
    clientVariant: str = LOGIN_FSR_CLIENT_VARIANT,
):
    require_admin_session(request)
    return InternalAccountEnvelope(
        data=InternalAccountAdminService(request.state.db, clientVariant).create_account(payload)
    )


@router.put("/accounts/{account_id}", response_model=InternalAccountEnvelope)
def admin_update_account(
    account_id: str,
    payload: UpdateInternalAccountRequest,
    request: Request,
    clientVariant: str = LOGIN_FSR_CLIENT_VARIANT,
):
    require_admin_session(request)
    return InternalAccountEnvelope(
        data=InternalAccountAdminService(request.state.db, clientVariant).update_account(account_id, payload)
    )


@router.post("/accounts/{account_id}/ban", response_model=InternalAccountEnvelope)
def admin_ban_account(
    account_id: str,
    payload: BanInternalAccountRequest,
    request: Request,
    clientVariant: str = LOGIN_FSR_CLIENT_VARIANT,
):
    require_admin_session(request)
    return InternalAccountEnvelope(
        data=InternalAccountAdminService(request.state.db, clientVariant).ban_account(account_id, payload)
    )


@router.post("/accounts/{account_id}/unban", response_model=InternalAccountEnvelope)
def admin_unban_account(
    account_id: str,
    request: Request,
    clientVariant: str = LOGIN_FSR_CLIENT_VARIANT,
):
    require_admin_session(request)
    return InternalAccountEnvelope(
        data=InternalAccountAdminService(request.state.db, clientVariant).unban_account(account_id)
    )


@router.delete("/accounts/{account_id}", response_model=ActionMessageResponse)
def admin_delete_account(
    account_id: str,
    request: Request,
    clientVariant: str = LOGIN_FSR_CLIENT_VARIANT,
):
    require_admin_session(request)
    InternalAccountAdminService(request.state.db, clientVariant).delete_account(account_id)
    return ActionMessageResponse(message="内部账号已删除")


@router.get("/devices", response_model=AuthDeviceListEnvelope)
def admin_list_devices(
    request: Request,
    q: str = "",
    statusFilter: str = "all",
    clientVariant: str = LOGIN_FSR_CLIENT_VARIANT,
):
    require_admin_session(request)
    return AuthDeviceListEnvelope(
        items=AdminDeviceService(request.state.db, clientVariant).list_devices(q, statusFilter)
    )


@router.put("/devices/{device_id}", response_model=AuthDeviceEnvelope)
def admin_update_device(
    device_id: str,
    payload: UpdateAuthDeviceRequest,
    request: Request,
    clientVariant: str = LOGIN_FSR_CLIENT_VARIANT,
):
    require_admin_session(request)
    return AuthDeviceEnvelope(
        data=AdminDeviceService(request.state.db, clientVariant).update_device(device_id, payload)
    )


@router.post("/devices/{device_id}/ban", response_model=AuthDeviceEnvelope)
def admin_ban_device(
    device_id: str,
    request: Request,
    clientVariant: str = LOGIN_FSR_CLIENT_VARIANT,
):
    require_admin_session(request)
    return AuthDeviceEnvelope(data=AdminDeviceService(request.state.db, clientVariant).ban_device(device_id))


@router.post("/devices/{device_id}/unban", response_model=AuthDeviceEnvelope)
def admin_unban_device(
    device_id: str,
    request: Request,
    clientVariant: str = LOGIN_FSR_CLIENT_VARIANT,
):
    require_admin_session(request)
    return AuthDeviceEnvelope(data=AdminDeviceService(request.state.db, clientVariant).unban_device(device_id))


@router.get("/tips", response_model=UsageTipListEnvelope)
def admin_list_tips(
    request: Request,
    q: str = "",
    published: str = "all",
    page: int = 1,
    pageSize: int = 20,
):
    require_admin_session(request)
    service = AdminUsageTipService(request.state.db)
    page = max(page, 1)
    pageSize = min(max(pageSize, 1), 100)
    items, total = service.list_tips(q, published, page, pageSize)
    total_pages = (total + pageSize - 1) // pageSize if total else 0
    return UsageTipListEnvelope(page=page, pageSize=pageSize, total=total, totalPages=total_pages, items=items)


@router.get("/tips/{tip_id}", response_model=UsageTipEnvelope)
def admin_get_tip(tip_id: str, request: Request):
    require_admin_session(request)
    service = AdminUsageTipService(request.state.db)
    try:
        tip = service.get_tip(tip_id)
    except ResourceNotFoundError as exception:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exception)},
        )
    return UsageTipEnvelope(data=tip)


@router.post("/tips", response_model=UsageTipEnvelope, status_code=status.HTTP_201_CREATED)
def admin_create_tip(payload: AdminSaveUsageTipRequest, request: Request):
    require_admin_session(request)
    return UsageTipEnvelope(data=AdminUsageTipService(request.state.db).create_tip(payload))


@router.put("/tips/{tip_id}", response_model=UsageTipEnvelope)
def admin_update_tip(tip_id: str, payload: AdminSaveUsageTipRequest, request: Request):
    require_admin_session(request)
    service = AdminUsageTipService(request.state.db)
    try:
        tip = service.update_tip(tip_id, payload)
    except ResourceNotFoundError as exception:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exception)},
        )
    return UsageTipEnvelope(data=tip)


@router.delete("/tips/{tip_id}", response_model=ActionMessageResponse)
def admin_delete_tip(tip_id: str, request: Request):
    require_admin_session(request)
    service = AdminUsageTipService(request.state.db)
    try:
        service.delete_tip(tip_id)
    except ResourceNotFoundError as exception:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exception)},
        )
    return ActionMessageResponse(message="使用技巧已删除")


@router.post("/tips/import-word", response_model=TipImportWordResponse)
def admin_import_tip_word(request: Request, file: UploadFile = File(...)):
    require_admin_session(request)
    return AdminUsageTipService(request.state.db).import_word(file)


@router.get("/routes", response_model=SharedRouteAdminListEnvelope)
def admin_list_routes(
    request: Request,
    q: str = "",
    privacyMode: str = "all",
    page: int = 1,
    pageSize: int = 10,
):
    require_admin_session(request)
    route_service = AdminRouteService(request.state.route_repository)
    page = max(page, 1)
    pageSize = min(max(pageSize, 1), 100)
    items, total = route_service.search_routes(q, privacyMode, page, pageSize)
    total_pages = (total + pageSize - 1) // pageSize if total else 0
    return SharedRouteAdminListEnvelope(
        page=page,
        pageSize=pageSize,
        total=total,
        totalPages=total_pages,
        items=items,
    )


@router.put("/routes/{route_id}", response_model=SharedRouteDetailEnvelope)
def admin_update_route(route_id: str, payload: CreateSharedRouteRequest, request: Request):
    require_admin_session(request)
    route_service = AdminRouteService(request.state.route_repository)
    try:
        route = route_service.update_route(route_id, payload)
    except ResourceNotFoundError as exception:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exception)},
        )
    return SharedRouteDetailEnvelope(data=route)


@router.delete("/routes/{route_id}", response_model=ActionMessageResponse)
def admin_delete_route(route_id: str, request: Request):
    require_admin_session(request)
    route_service = AdminRouteService(request.state.route_repository)
    try:
        route_service.delete_route(route_id)
    except ResourceNotFoundError as exception:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exception)},
        )
    return ActionMessageResponse(message="共享路线已删除")


@router.get("/nfc", response_model=SharedNfcListEnvelope)
def admin_list_nfc(
    request: Request,
    q: str = "",
    page: int = 1,
    pageSize: int = 10,
):
    require_admin_session(request)
    nfc_service = AdminNfcService(request.state.nfc_repository)
    page = max(page, 1)
    pageSize = min(max(pageSize, 1), 100)
    items, total = nfc_service.search_entries(q, page, pageSize)
    total_pages = (total + pageSize - 1) // pageSize if total else 0
    return SharedNfcListEnvelope(
        page=page,
        pageSize=pageSize,
        total=total,
        totalPages=total_pages,
        items=items,
    )


@router.put("/nfc/{entry_id}", response_model=SharedNfcEnvelope)
def admin_update_nfc(entry_id: str, payload: CreateSharedNfcRequest, request: Request):
    require_admin_session(request)
    nfc_service = AdminNfcService(request.state.nfc_repository)
    try:
        entry = nfc_service.update_entry(entry_id, payload)
    except ResourceNotFoundError as exception:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exception)},
        )
    return SharedNfcEnvelope(data=entry)


@router.delete("/nfc/{entry_id}", response_model=ActionMessageResponse)
def admin_delete_nfc(entry_id: str, request: Request):
    require_admin_session(request)
    nfc_service = AdminNfcService(request.state.nfc_repository)
    try:
        nfc_service.delete_entry(entry_id)
    except ResourceNotFoundError as exception:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exception)},
        )
    return ActionMessageResponse(message="共享 NFC 已删除")
