from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import get_db, get_release_identity
from app.application.schemas.access_policy_schemas import (
    AccessPolicyEnvelope,
    AccessPolicyRequest,
    AccessStatusEnvelope,
)
from app.application.services.access_policy_service import AccessPolicyService
from app.web.auth import require_admin_session

router = APIRouter()


@router.get("/app/access", response_model=AccessStatusEnvelope)
def access_status(response: Response, channel: str = Query(""), installId: str = Query(""),
                  db=Depends(get_db), identity=Depends(get_release_identity)) -> AccessStatusEnvelope:
    """客户端启动确认：allowed=False 时客户端不得使用。"""
    response.headers["Cache-Control"] = "no-store"
    return AccessStatusEnvelope(**AccessPolicyService(db).status(identity[0]))


@router.get("/admin/access-policy", response_model=AccessPolicyEnvelope)
def admin_get_policy(response: Response, db=Depends(get_db),
                     _admin=Depends(require_admin_session)) -> AccessPolicyEnvelope:
    response.headers["Cache-Control"] = "no-store"
    return AccessPolicyEnvelope(**AccessPolicyService(db).policy())


@router.put("/admin/access-policy", response_model=AccessPolicyEnvelope)
def admin_put_policy(payload: AccessPolicyRequest, db=Depends(get_db),
                     _admin=Depends(require_admin_session)) -> AccessPolicyEnvelope:
    return AccessPolicyEnvelope(**AccessPolicyService(db).update(
        payload.serviceEnabled, payload.message, payload.scope))
