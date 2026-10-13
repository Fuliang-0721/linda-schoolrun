import hashlib
import time
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

from app.api.dependencies import get_db
from app.api.routes.client_telemetry import router
from app.application.schemas.client_telemetry_schemas import ClientTelemetryRequest
from app.application.services.client_telemetry_service import ClientTelemetryService
from app.core.config import settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.migrations import migrate_schema
from app.infrastructure.db.models.client_telemetry import ClientTelemetryModel as Client
from app.web.routes.admin_panel import router as web_router


@pytest.fixture
def env():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Client.__table__.create(engine)
    db = sessionmaker(bind=engine)()
    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key="test-only")
    app.include_router(router, prefix="/api")
    app.include_router(web_router)
    app.dependency_overrides[get_db] = lambda: db

    @app.post("/test-login")
    def login(request: __import__("fastapi").Request):
        request.session["admin_username"] = settings.admin_username
        return {}

    with TestClient(app) as client:
        yield client, db
    db.close()
    engine.dispose()


def payload(**changes):
    data = dict(installId="a" * 32, token="b" * 64, sequence=1, versionName="v1.16D",
                versionCode=20126, deviceModel="Test phone", androidSdk=36, launches=1,
                simulationCount=2, simulationSeconds=60, locationStatus="disabled")
    data.update(changes)
    return data


def fix():
    return dict(latitude=31.2, longitude=121.4, accuracy=20, capturedAt=int(time.time() * 1000))


def test_install_dedup_and_monotonic_totals(env):
    client, db = env
    assert client.post("/api/client-telemetry", json=payload()).status_code == 200
    assert client.post("/api/client-telemetry", json=payload()).json()["data"]["accepted"] is False
    client.post("/api/client-telemetry", json=payload(sequence=3, launches=3))
    client.post("/api/client-telemetry", json=payload(sequence=2, launches=20))
    assert db.query(Client).count() == 1
    row = db.query(Client).one()
    assert row.launches == 3
    assert row.token_hash == hashlib.sha256(("b" * 64).encode()).hexdigest()


def test_latest_location_replaces_and_failed_fix_clears(env):
    client, db = env
    client.post("/api/client-telemetry", json=payload(locationStatus="available", location=fix()))
    assert db.query(Client).one().latitude == 31.2
    client.post("/api/client-telemetry", json=payload(sequence=2, locationStatus="mock_active"))
    row = db.query(Client).one()
    assert row.latitude is None and row.longitude is None and row.location_at is None
    assert row.location_status == "mock_active"


@pytest.mark.parametrize("change", [
    {"locationStatus": "available"}, {"locationStatus": "disabled", "location": fix()},
    {"locationStatus": "available", "location": {**fix(), "latitude": 91}},
    {"locationStatus": "available", "location": {**fix(), "accuracy": 0}},
    {"locationStatus": "available", "location": {**fix(), "capturedAt": 1}},
    {"locationStatus": "available", "location": {**fix(), "capturedAt": 9999999999999}},
    {"imei": "forbidden"}, {"sequence": 0}, {"launches": -1}, {"installId": "bad"},
])
def test_invalid_or_sensitive_payload_rejected(env, change):
    client, db = env
    assert client.post("/api/client-telemetry", json=payload(**change)).status_code == 422
    assert db.query(Client).count() == 0


def test_admin_auth_pagination_and_no_token_disclosure(env):
    client, _ = env
    client.post("/api/client-telemetry", json=payload())
    assert client.get("/api/admin/client-telemetry").status_code == 401
    assert client.get("/admin/clients", follow_redirects=False).status_code == 303
    client.post("/test-login")
    response = client.get("/api/admin/client-telemetry").json()
    assert response["stats"]["installations"] == 1
    assert response["stats"]["dailyActive"] == 1
    assert response["stats"]["monthlyActive"] == 1
    assert "token" not in str(response)
    assert client.get("/api/admin/client-telemetry?pageSize=101").status_code == 422
    html = client.get("/admin/clients")
    assert html.status_code == 200 and "v1.16D" in html.text
    assert html.headers["cache-control"] == "no-store"


def test_foreign_install_token_cannot_modify_or_erase(env):
    client, db = env
    client.post("/api/client-telemetry", json=payload())
    assert client.post("/api/client-telemetry", json=payload(sequence=2, token="c" * 64)).status_code == 403
    assert client.post("/api/client-telemetry/erase", json={"installId": "a" * 32, "token": "c" * 64}).status_code == 403
    assert db.query(Client).count() == 1


def test_erasure_idempotent(env):
    client, db = env
    client.post("/api/client-telemetry", json=payload(locationStatus="available", location=fix()))
    for _ in range(2):
        assert client.post("/api/client-telemetry/erase", json={"installId": "a" * 32, "token": "b" * 64}).status_code == 200
    assert db.query(Client).count() == 0


def test_active_windows_use_shanghai_calendar(env):
    _, db = env
    service = ClientTelemetryService(db)
    service.upload(ClientTelemetryRequest(**payload()))
    today = datetime.now(timezone(timedelta(hours=8))).replace(hour=0, minute=0, second=0, microsecond=0)
    row = db.query(Client).one()
    row.last_seen = int((today - timedelta(seconds=1)).timestamp() * 1000)
    db.commit()
    assert service.dashboard()["stats"]["dailyActive"] == 0
    assert service.dashboard()["stats"]["monthlyActive"] == 1
    row.last_seen = int((today - timedelta(days=30)).timestamp() * 1000)
    db.commit()
    assert service.dashboard()["stats"]["monthlyActive"] == 0


def test_legacy_database_migration_idempotent():
    engine = create_engine("sqlite://")
    migrate_schema(engine)
    migrate_schema(engine)
    assert "client_telemetry" in inspect(engine).get_table_names()
    # No event or location-history table is introduced.
    assert {c["name"] for c in inspect(engine).get_columns("client_telemetry")} >= {"latitude", "token_hash", "sequence"}
    engine.dispose()
