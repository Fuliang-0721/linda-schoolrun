from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import get_db, get_release_identity
from app.application.schemas.client_config_schemas import (
    AppClientConfigEnvelope,
    AppClientConfigResponse,
)
from app.application.services.app_notice_service import AppNoticeService
from app.core.config import settings

router = APIRouter()


@router.get("/client-config", response_model=AppClientConfigEnvelope)
def get_client_config(response: Response, channel: str = Query(""), installId: str = Query(""),
                      db=Depends(get_db), identity=Depends(get_release_identity)) -> AppClientConfigEnvelope:
    """启动配置：公告 + 服务开关。channel=internal 时 scope=public_only 的停止策略不生效。"""
    response.headers["Cache-Control"] = "no-store"
    from app.application.services.access_policy_service import AccessPolicyService
    access = AccessPolicyService(db).status(identity[0])["data"]
    notice = AppNoticeService(db).get_notice()
    return AppClientConfigEnvelope(
        data=AppClientConfigResponse(
            noticeTitle=notice.title,
            noticeMessage=notice.message,
            qqGroupNumber=notice.qqGroupNumber,
            bilibiliText=notice.bilibiliText,
            bilibiliUrl=notice.bilibiliUrl,
            killSwitch=not access["allowed"],
            killSwitchMessage=access["message"] or (
                settings.client_kill_switch_message if settings.client_kill_switch else ""),
        )
    )
