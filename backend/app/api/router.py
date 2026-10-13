from fastapi import APIRouter

from app.api.routes.admin import router as admin_router
from app.api.routes.admin_releases import router as admin_releases_router
from app.api.routes.app_access import router as app_access_router
from app.api.routes.app_logs import router as app_logs_router
from app.api.routes.admin_logs import router as admin_logs_router
from app.api.routes.app_version import router as app_version_router
from app.api.routes.auth import router as auth_router
from app.api.routes.client_config import router as client_config_router
from app.api.routes.health import router as health_router
from app.api.routes.shared_nfc import router as shared_nfc_router
from app.api.routes.shared_routes import router as shared_routes_router
from app.api.routes.shared_simulation_configs import router as shared_simulation_configs_router
from app.api.routes.usage_tips import router as usage_tips_router

from app.api.routes.client_telemetry import router as telemetry_router

api_router = APIRouter()
api_router.include_router(telemetry_router, tags=["client-telemetry"])
api_router.include_router(health_router, tags=["health"])
api_router.include_router(app_access_router, tags=["app-access"])
api_router.include_router(client_config_router, tags=["client-config"])
api_router.include_router(app_version_router, tags=["app-version"])
api_router.include_router(admin_logs_router, tags=["admin-logs"])
api_router.include_router(admin_router, tags=["admin"])
api_router.include_router(admin_releases_router, tags=["admin-releases"])
api_router.include_router(app_logs_router, tags=["app-logs"])
api_router.include_router(auth_router, tags=["auth"])
api_router.include_router(usage_tips_router, tags=["tips"])
api_router.include_router(shared_routes_router, prefix="/shared/routes", tags=["shared-routes"])
api_router.include_router(shared_nfc_router, prefix="/shared/nfc", tags=["shared-nfc"])
api_router.include_router(shared_simulation_configs_router, tags=["shared-simulation-configs"])
