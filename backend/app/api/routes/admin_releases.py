from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_db
from app.application.schemas.admin_schemas import ActionMessageResponse
from app.application.schemas.app_release_schemas import (
    AppReleaseEnvelope,
    AppReleaseListEnvelope,
    CreateAppReleaseRequest,
    UpdateAppReleaseRequest,
    UploadedBundleEnvelope,
)
from app.application.services.app_release_service import AppReleaseService
from app.web.auth import require_admin_session

router = APIRouter(prefix="/admin")

MAX_BUNDLE_BYTES = 400 * 1024 * 1024


def _require_release(service: AppReleaseService, release_id: str):
    release = service.get_release(release_id)
    if release is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="发布记录不存在")
    return release


@router.get("/releases", response_model=AppReleaseListEnvelope)
def list_releases(
    packageName: str | None = None,
    channel: str | None = None,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> AppReleaseListEnvelope:
    service = AppReleaseService(db)
    return AppReleaseListEnvelope(items=service.list_releases(packageName, channel))


@router.post("/releases", response_model=AppReleaseEnvelope)
def create_release(
    payload: CreateAppReleaseRequest,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> AppReleaseEnvelope:
    service = AppReleaseService(db)
    return AppReleaseEnvelope(data=service.create_release(payload))


# 注意：必须放在 /releases/{release_id} 之前，否则会被后者抢先匹配
@router.post("/releases/upload", response_model=UploadedBundleEnvelope)
def upload_bundle(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> UploadedBundleEnvelope:
    """上传 APK 到服务器发布目录，返回 sha256/size/下载地址，供创建发布记录时使用。"""
    service = AppReleaseService(db)
    return UploadedBundleEnvelope(data=service.save_bundle_stream(file.filename or "bundle.apk", file.file, MAX_BUNDLE_BYTES))


@router.post("/releases/{release_id}", response_model=AppReleaseEnvelope)
def update_release(
    release_id: str,
    payload: UpdateAppReleaseRequest,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> AppReleaseEnvelope:
    service = AppReleaseService(db)
    release = _require_release(service, release_id)
    try:
        updated = service.update_release(release, payload)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return AppReleaseEnvelope(data=updated)


@router.post("/releases/{release_id}/publish", response_model=AppReleaseEnvelope)
def publish_release(
    release_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> AppReleaseEnvelope:
    service = AppReleaseService(db)
    release = _require_release(service, release_id)
    return AppReleaseEnvelope(data=service.publish_release(release))


@router.post("/releases/{release_id}/revoke", response_model=AppReleaseEnvelope)
def revoke_release(
    release_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> AppReleaseEnvelope:
    service = AppReleaseService(db)
    release = _require_release(service, release_id)
    return AppReleaseEnvelope(data=service.revoke_release(release))


@router.delete("/releases/{release_id}", response_model=ActionMessageResponse)
def delete_release(
    release_id: str,
    db: Session = Depends(get_db),
    _admin: str = Depends(require_admin_session),
) -> ActionMessageResponse:
    service = AppReleaseService(db)
    release = _require_release(service, release_id)
    service.delete_release(release)
    return ActionMessageResponse(message="已删除")
