from fastapi import APIRouter, Depends, Query, Response

from app.api.dependencies import get_db
from app.application.schemas.client_telemetry_schemas import ClientIdentity, ClientTelemetryRequest
from app.application.services.client_telemetry_service import ClientTelemetryService
from app.web.auth import require_admin_session

router = APIRouter()


@router.post("/client-telemetry")
def upload(payload: ClientTelemetryRequest, db=Depends(get_db)):
    return ClientTelemetryService(db).upload(payload)


@router.post("/client-telemetry/erase")
def erase(payload: ClientIdentity, db=Depends(get_db)):
    return ClientTelemetryService(db).erase(payload)


@router.get("/admin/client-telemetry")
def dashboard(response: Response, page: int = Query(1, ge=1), pageSize: int = Query(30, ge=1, le=100),
              db=Depends(get_db), _admin=Depends(require_admin_session)):
    response.headers["Cache-Control"] = "no-store"
    return ClientTelemetryService(db).dashboard(page, pageSize)


@router.delete("/admin/client-telemetry")
def delete_all(db=Depends(get_db), _admin=Depends(require_admin_session)):
    """清空全部客户端统计记录（管理端）。"""
    return ClientTelemetryService(db).delete_all()


@router.delete("/admin/client-telemetry/{install_id}")
def delete_one(install_id: str, db=Depends(get_db), _admin=Depends(require_admin_session)):
    """删除指定安装的统计与位置记录（管理端）。"""
    return ClientTelemetryService(db).delete(install_id)
