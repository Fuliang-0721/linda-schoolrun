from pathlib import Path

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.api.dependencies import get_db
from app.application.services.device_log_service import DeviceLogService
from app.core.config import settings
from app.core.exceptions import ResourceNotFoundError
from app.web.auth import is_admin_authenticated, require_admin_session

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "templates"))


@router.get("/admin/clients", response_class=HTMLResponse)
def admin_clients(request: Request, page: int = 1, db=Depends(get_db)):
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin", status_code=303)
    from app.application.services.client_telemetry_service import ClientTelemetryService
    response = templates.TemplateResponse(request=request, name="admin_clients.html",
        context=ClientTelemetryService(db).dashboard(max(1, page)))
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/admin/access", response_class=HTMLResponse)
def admin_access_page(request: Request, db=Depends(get_db)):
    if not is_admin_authenticated(request):
        return RedirectResponse(url="/admin", status_code=303)
    from app.application.services.access_policy_service import AccessPolicyService
    response = templates.TemplateResponse(request=request, name="admin_access.html",
        context={"authenticated": True,
                 "admin_username": request.session.get("admin_username"),
                 **AccessPolicyService(db).policy()})
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/admin", response_class=HTMLResponse)
def admin_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin.html",
        context={
            "authenticated": is_admin_authenticated(request),
            "admin_username": request.session.get("admin_username"),
            "client_variant": settings.internal_auth_variant,
        },
    )


@router.get("/admin/ops", response_class=HTMLResponse)
@router.get("/ops-admin", response_class=HTMLResponse)
def admin_ops_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="admin_ops.html",
        context={
            "authenticated": is_admin_authenticated(request),
            "admin_username": request.session.get("admin_username"),
            "client_variant": settings.internal_auth_variant,
        },
    )


@router.get("/admin/logs", response_class=HTMLResponse)
def admin_logs_page(
    request: Request,
    installId: str = "",
    reason: str = "",
    q: str = "",
    page: int = 1,
    pageSize: int = 20,
    db=Depends(get_db),
):
    """运行日志看板：客户端崩溃现场与手动反馈。"""
    authenticated = is_admin_authenticated(request)
    filters = {"installId": installId, "reason": reason, "q": q}
    context = {
        "authenticated": authenticated,
        "admin_username": request.session.get("admin_username"),
        "filters": filters,
        "items": [],
        "stats": {"total": 0, "crash": 0, "sizeText": "0 KB"},
        "page": 1,
        "totalPages": 0,
        "total": 0,
        "pageSize": pageSize,
        "page_url": lambda target: "/admin/logs",
    }
    if not authenticated:
        return templates.TemplateResponse(request=request, name="admin_logs.html", context=context)

    service = DeviceLogService(db)
    safe_size = max(1, min(pageSize, 100))
    summaries, total = service.list_logs(
        page=max(1, page), page_size=safe_size, install_id=installId, reason=reason, keyword=q
    )
    stats = service.stats()
    total_pages = (total + safe_size - 1) // safe_size if total else 0

    items = []
    for summary in summaries:
        try:
            log_text = service.get_log(summary.id).logText
        except ResourceNotFoundError:
            log_text = ""
        items.append({
            "id": summary.id,
            "installId": summary.installId,
            "versionName": summary.versionName or "-",
            "versionCode": summary.versionCode,
            "deviceModel": summary.deviceModel or "-",
            "androidSdk": summary.androidSdk,
            "reason": summary.reason,
            "sizeText": _format_size(summary.sizeBytes),
            "timeText": _format_time(summary.createdAt),
            "logText": log_text,
        })

    def page_url(target_page: int) -> str:
        params = {
            "installId": installId,
            "reason": reason,
            "q": q,
            "pageSize": safe_size,
            "page": target_page,
        }
        return "/admin/logs?" + urlencode({k: v for k, v in params.items() if v not in ("", None)})

    context.update({
        "items": items,
        "stats": {
            "total": stats["total"],
            "crash": stats["crash"],
            "sizeText": _format_size(stats["totalBytes"]),
        },
        "page": max(1, page),
        "totalPages": total_pages,
        "total": total,
        "pageSize": safe_size,
        "page_url": page_url,
    })
    return templates.TemplateResponse(request=request, name="admin_logs.html", context=context)


@router.post("/admin/logs/{log_id}/delete")
def admin_logs_delete(log_id: str, request: Request, db=Depends(get_db)):
    require_admin_session(request)
    try:
        DeviceLogService(db).delete_log(log_id)
    except ResourceNotFoundError:
        pass
    return RedirectResponse(url="/admin/logs", status_code=303)


def _format_size(size_bytes: int) -> str:
    if size_bytes <= 0:
        return "0 KB"
    value = size_bytes / 1024.0
    if value >= 1024:
        return "%.1f MB" % (value / 1024.0)
    return "%.1f KB" % value


def _format_time(timestamp_millis: int) -> str:
    if not timestamp_millis:
        return "-"
    zone = timezone(timedelta(hours=8))
    return datetime.fromtimestamp(timestamp_millis / 1000.0, tz=zone).strftime("%Y-%m-%d %H:%M:%S")


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return Response(status_code=204)
