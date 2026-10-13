from fastapi import APIRouter, Depends, Request

from app.api.dependencies import get_db, require_current_account
from app.application.schemas.device_log_schemas import (
    UploadDeviceLogEnvelope,
    UploadDeviceLogRequest,
)
from app.application.services.device_log_service import DeviceLogService
from app.application.schemas.app_log_schemas import (
    InternalSoftwareNameEnvelope,
    InternalSoftwareNameListEnvelope,
    SubmitInternalSoftwareNameRequest,
    UploadAppLogEnvelope,
    UploadAppLogRequest,
)
from app.application.schemas.auth_schemas import AccountResponse
from app.application.services.app_log_service import AppLogService

router = APIRouter(prefix="/app-logs")


@router.get("/software-names", response_model=InternalSoftwareNameListEnvelope)
def list_software_names(db=Depends(get_db)) -> InternalSoftwareNameListEnvelope:
    return InternalSoftwareNameListEnvelope(items=AppLogService(db).list_approved_software_names())


@router.post("/software-name-submissions", response_model=InternalSoftwareNameEnvelope)
def submit_software_name(
        payload: SubmitInternalSoftwareNameRequest,
        db=Depends(get_db),
        account: AccountResponse = Depends(require_current_account),
) -> InternalSoftwareNameEnvelope:
    return InternalSoftwareNameEnvelope(data=AppLogService(db).submit_software_name(payload, account))


@router.post("/device", response_model=UploadDeviceLogEnvelope)
def upload_device_log(
        payload: UploadDeviceLogRequest,
        request: Request,
        db=Depends(get_db),
) -> UploadDeviceLogEnvelope:
    """客户端运行日志上报（崩溃现场 / 用户手动反馈），供后台看板排查。"""
    client_ip = request.client.host if request.client else ""
    return UploadDeviceLogEnvelope(data=DeviceLogService(db).upload(payload, client_ip))


@router.post("", response_model=UploadAppLogEnvelope)
def upload_app_log(
        payload: UploadAppLogRequest,
        db=Depends(get_db),
        account: AccountResponse = Depends(require_current_account),
) -> UploadAppLogEnvelope:
    return UploadAppLogEnvelope(data=AppLogService(db).upload_log(payload, account))


from app.application.schemas.client_telemetry_schemas import ClientIdentity

@router.post("/device/erase")
def erase_device_logs(payload: ClientIdentity, db=Depends(get_db)):
    import hashlib
    from app.infrastructure.db.models.device_log import DeviceLogModel
    db.query(DeviceLogModel).filter(DeviceLogModel.install_id == payload.installId,
        DeviceLogModel.token_hash == hashlib.sha256(payload.token.encode()).hexdigest()).delete(synchronize_session=False)
    db.commit()
    return {"data": {"erased": True}}
