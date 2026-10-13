from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.migrations import migrate_schema
from app.infrastructure.repositories.shared_nfc_sql_repository import SharedNfcSqlRepository
from app.infrastructure.repositories.shared_route_sql_repository import SharedRouteSqlRepository
from app.infrastructure.db.session import engine
from app.infrastructure.db.session import SessionLocal
from app.infrastructure.db.models import app_log as app_log_models  # noqa: F401
from app.infrastructure.db.models import app_notice as app_notice_models  # noqa: F401
from app.infrastructure.db.models import app_release as app_release_models  # noqa: F401
from app.infrastructure.db.models import auth as auth_models  # noqa: F401
from app.infrastructure.db.models import nfc as nfc_models  # noqa: F401
from app.infrastructure.db.models import route as route_models  # noqa: F401
from app.infrastructure.db.models import simulation_config as simulation_config_models  # noqa: F401
from app.infrastructure.db.models import tip as tip_models  # noqa: F401
from app.web.routes.admin_panel import router as admin_panel_router


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings.validate_security()
    if settings.auto_create_tables:
        Base.metadata.create_all(bind=engine)
        migrate_schema(engine)
    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.middleware("http")
async def inject_repositories(request, call_next):
    db = SessionLocal()
    request.state.db = db
    request.state.route_repository = SharedRouteSqlRepository(db)
    request.state.nfc_repository = SharedNfcSqlRepository(db)
    try:
        response = await call_next(request)
    finally:
        db.close()
    return response

app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(admin_panel_router)
from app.api.routes.downloads import router as download_router
app.include_router(download_router)


def _sanitize_validation_value(value):
    """请求体解析失败时 FastAPI 会把原始 bytes 放进错误详情，直接序列化会 500。"""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (bytes, bytearray)):
        return f"<{len(value)} bytes>"
    if isinstance(value, dict):
        return {str(key): _sanitize_validation_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_validation_value(item) for item in value]
    return str(value)


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(_request, exc: RequestValidationError):
    errors = []
    for error in exc.errors():
        item = {key: value for key, value in error.items() if key != "input"}
        item["input"] = _sanitize_validation_value(error.get("input"))
        errors.append(item)
    return JSONResponse(status_code=422, content={"detail": errors})


@app.middleware("http")
async def guard_requests(request, call_next):
    from urllib.parse import urlsplit
    from fastapi import HTTPException
    from app.core.request_guard import limiter
    from app.web.auth import is_admin_authenticated
    path = request.url.path
    write = request.method not in {"GET", "HEAD", "OPTIONS"}
    admin = path.startswith("/api/admin/") or path == "/api/admin" or path.startswith("/admin/") or path in {"/api/shared/nfc", "/api/shared/routes"}
    if write and admin:
        origin = request.headers.get("origin")
        public = urlsplit(settings.admin_public_origin or settings.release_public_base_url)
        expected = (f"{public.scheme}://{public.netloc}" if public.scheme and public.netloc else str(request.base_url).rstrip("/"))
        if origin and origin != expected:
            return JSONResponse({"detail": "不允许跨源管理请求"}, status_code=403)
        if request.session and not origin:
            return JSONResponse({"detail": "管理写请求必须提供同源 Origin"}, status_code=403)
    if path == "/api/admin/releases/upload" and not is_admin_authenticated(request):
        return JSONResponse({"detail": "未登录"}, status_code=401)
    if write:
        try:
            ip = request.client.host if request.client else "unknown"
            if path.endswith("/login"):
                limiter.check(("login", ip), 10)
            elif path.startswith(("/api/app-logs", "/api/client-telemetry")):
                limiter.check(("ingest", ip), 60)
                limiter.check(("ingest-global",), 600)
            # Small API bodies are bounded before JSON parsing. APKs are streamed by the upload service.
            if path != "/api/admin/releases/upload":
                body = bytearray()
                async for chunk in request.stream():
                    body.extend(chunk)
                    if len(body) > 2 * 1024 * 1024:
                        return JSONResponse({"detail": "请求内容过大"}, status_code=413)
                request._body = bytes(body)
        except HTTPException as exc:
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=exc.headers)
    return await call_next(request)

# Session must wrap guard_requests so authentication is available before multipart parsing.
app.add_middleware(SessionMiddleware, secret_key=settings.admin_session_secret,
                   session_cookie="schoolrun_admin_session", same_site="strict",
                   https_only=settings.app_env.lower() == "production")
