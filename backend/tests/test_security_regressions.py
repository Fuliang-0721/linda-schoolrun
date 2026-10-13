import io
import json
import base64
import pytest
from fastapi.testclient import TestClient
from itsdangerous import TimestampSigner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.core.config import settings, Settings
from app.api.dependencies import get_db
from app.infrastructure.db.base import Base
from app.application.services.app_release_service import AppReleaseService
from app.application.schemas.app_release_schemas import CreateAppReleaseRequest
from app.core.safe_html import sanitize_html


@pytest.fixture
def db():
    engine = create_engine('sqlite://', poolclass=StaticPool, connect_args={'check_same_thread': False})
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def client(db, monkeypatch):
    monkeypatch.setattr(settings, "app_env", "development")
    monkeypatch.setattr(settings, "admin_public_origin", "")
    monkeypatch.setattr(settings, "release_public_base_url", "")
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def admin_cookie():
    return TimestampSigner(settings.admin_session_secret).sign(base64.b64encode(json.dumps({'admin_username': settings.admin_username}).encode())).decode()


def test_production_rejects_default_credentials():
    with pytest.raises(RuntimeError):
        Settings(app_env='production', _env_file=None).validate_security()


def test_production_secrets_must_be_distinct():
    with pytest.raises(RuntimeError):
        Settings(app_env='production', admin_password='strong-password-for-test', admin_session_secret='s'*40,
                 mobile_auth_secret='s'*40, _env_file=None).validate_security()


def test_cross_origin_admin_write_rejected(client):
    client.cookies.set('schoolrun_admin_session', admin_cookie())
    assert client.delete('/api/admin/client-telemetry', headers={'Origin': 'https://attacker.test'}).status_code == 403
    assert client.delete('/api/admin/client-telemetry').status_code == 403
    assert client.delete('/api/admin/client-telemetry', headers={'Origin': 'http://testserver'}).status_code == 200


def test_internal_parameter_is_not_authentication(client):
    client.cookies.set('schoolrun_admin_session', admin_cookie())
    r = client.put('/api/admin/access-policy', json={'serviceEnabled': False, 'message': '', 'scope': 'public_only'}, headers={'Origin': 'http://testserver'})
    assert r.status_code == 200
    client.cookies.clear()
    assert client.get('/api/app/access?channel=internal').json()['data']['allowed'] is False


def test_public_id_cannot_discover_targeted_release(client, db, tmp_path):
    s = AppReleaseService(db, str(tmp_path))
    s.create_release(CreateAppReleaseRequest(packageName='test.app', channel='internal', versionCode=2,
        versionName='v2', targetInstallIds=['known-install'], status='published'))
    r = client.get('/api/app/version', params={'package':'test.app', 'channel':'internal', 'versionCode':1, 'installId':'known-install'})
    assert r.status_code == 200
    assert r.json()['data']['update'] is False


def test_gray_release_falls_back_to_full_release(db, tmp_path):
    s = AppReleaseService(db, str(tmp_path))
    for code, percent in [(2,100),(3,0)]:
        s.create_release(CreateAppReleaseRequest(packageName='test.app', versionCode=code,
            versionName=str(code), rolloutPercent=percent, status='published'))
    assert s.resolve_version('test.app', 'stable', 1, 'arm64-v8a', 'x').versionCode == 2


def test_uploaded_objects_are_immutable_and_bounded(db, tmp_path):
    s = AppReleaseService(db, str(tmp_path))
    a = s.save_bundle('same.apk', b'old')
    b = s.save_bundle('same.apk', b'new')
    assert a.fileName != b.fileName
    assert (tmp_path / a.fileName).read_bytes() == b'old'
    with pytest.raises(Exception) as caught:
        s.save_bundle_stream('large.apk', io.BytesIO(b'12345'), max_bytes=4)
    assert caught.value.status_code == 413
    assert not list(tmp_path.glob('.upload-*'))


def test_html_cannot_keep_script_or_event_handlers():
    result = sanitize_html('<p onclick="alert(1)">hello<script>alert(1)</script><img src=x onerror="alert(2)"><a href="javascript:alert(3)">link</a></p>')
    assert 'hello' in result
    assert all(value not in result for value in ['script', 'onclick', 'onerror', 'javascript', '<img'])


def test_log_delete_requires_matching_install_token(client, db):
    from app.infrastructure.db.models.device_log import DeviceLogModel
    import hashlib
    row=DeviceLogModel(id='log-test', install_id='a'*32, token_hash=hashlib.sha256(('b'*64).encode()).hexdigest(),
        log_text='test', size_bytes=4, created_at=1)
    db.add(row); db.commit()
    assert client.post('/api/app-logs/device/erase', json={'installId':'a'*32, 'token':'c'*64}).status_code == 200
    assert db.get(DeviceLogModel, 'log-test') is not None
    client.post('/api/app-logs/device/erase', json={'installId':'a'*32, 'token':'b'*64})
    db.expire_all()
    assert db.get(DeviceLogModel, 'log-test') is None


def test_admin_templates_render(client):
    assert client.get('/admin').status_code == 200
    assert client.get('/admin/ops').status_code == 200


def test_download_needs_token_and_supports_range(client, monkeypatch, tmp_path):
    from app.core.download_tokens import signer
    monkeypatch.setattr(settings, 'releases_dir', str(tmp_path))
    (tmp_path / 'test.apk').write_bytes(b'0123456789')
    assert client.get('/dl/test.apk').status_code == 403
    token = signer().dumps('test.apk')
    result = client.get('/dl/test.apk', params={'token':token}, headers={'Range':'bytes=2-4'})
    assert result.status_code == 206
    assert result.content == b'234'
    assert client.get('/dl/other.apk', params={'token':token}).status_code == 403
