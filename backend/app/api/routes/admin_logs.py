from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_db
from app.application.schemas.admin_schemas import ActionMessageResponse
from app.application.schemas.device_log_schemas import (
    DeviceLogDetailEnvelope,
    DeviceLogListEnvelope,
)
from app.application.services.device_log_service import DeviceLogService
from app.core.exceptions import ResourceNotFoundError
from app.web.auth import require_admin_session

router = APIRouter(prefix="/admin")


@router.get("/logs", response_model=DeviceLogListEnvelope)
def list_device_logs(
    installId: str = "",
    reason: str = "",
    q: str = "",
    page: int = Query(default=1, ge=1),
    pageSize: int = Query(default=20, ge=1, le=100),
    db=Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> DeviceLogListEnvelope:
    items, total = DeviceLogService(db).list_logs(
        page=page, page_size=pageSize, install_id=installId, reason=reason, keyword=q
    )
    total_pages = (total + pageSize - 1) // pageSize if total else 0
    return DeviceLogListEnvelope(
        page=page, pageSize=pageSize, total=total, totalPages=total_pages, items=items
    )


@router.get("/logs/{log_id}", response_model=DeviceLogDetailEnvelope)
def get_device_log(
    log_id: str,
    db=Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> DeviceLogDetailEnvelope:
    service = DeviceLogService(db)
    try:
        return DeviceLogDetailEnvelope(data=service.get_log(log_id))
    except ResourceNotFoundError as exception:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exception)) from exception


@router.delete("/logs/{log_id}", response_model=ActionMessageResponse)
def delete_device_log(
    log_id: str,
    db=Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> ActionMessageResponse:
    service = DeviceLogService(db)
    try:
        service.delete_log(log_id)
    except ResourceNotFoundError as exception:
        from fastapi import HTTPException, status

        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exception)) from exception
    return ActionMessageResponse(message=f"已删除日志 {log_id}")
