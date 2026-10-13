from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.dependencies import get_db, get_release_identity
from app.application.schemas.app_release_schemas import (
    AppReleaseHistoryEnvelope,
    AppVersionEnvelope,
)
from app.application.services.app_release_service import AppReleaseService

router = APIRouter()


@router.get("/app/version", response_model=AppVersionEnvelope)
def get_app_version(
    package_name: str = Query(..., alias="package", min_length=1, max_length=128),
    channel: str = Query(default="stable", max_length=32),
    version_code: int = Query(default=0, alias="versionCode", ge=0),
    abi: str = Query(default="", max_length=32),
    install_id: str = Query(default="", alias="installId", max_length=128),
    db: Session = Depends(get_db),
    identity=Depends(get_release_identity),
) -> AppVersionEnvelope:
    """客户端启动时检查更新。

    - 无更新时返回 `update=false`（仍带服务端最新版本号，便于排查）
    - 有更新时返回完整下载信息；`force=true` 表示不可取消，客户端必须拦截使用
    - 灰度：携带随机 `installId`（非硬件标识）时按比例下发
    """
    service = AppReleaseService(db)
    return AppVersionEnvelope(
        data=service.resolve_version(package_name, identity[0], version_code, abi, identity[1] or install_id, allow_targeted=bool(identity[1]))
    )


@router.get("/app/releases", response_model=AppReleaseHistoryEnvelope)
def list_app_releases(
    package_name: str = Query(..., alias="package", min_length=1, max_length=128),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
) -> AppReleaseHistoryEnvelope:
    """公开的版本更新记录（客户端「更新记录」页面用）。"""
    return AppReleaseHistoryEnvelope(
        items=AppReleaseService(db).list_history(package_name, limit)
    )
