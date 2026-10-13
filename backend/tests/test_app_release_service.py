"""AppReleaseService 单元测试（使用 SQLite 内存库，不依赖 MySQL）。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.schemas.app_release_schemas import CreateAppReleaseRequest
from app.application.services.app_release_service import AppReleaseService
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.app_release import AppReleaseModel  # noqa: F401

PKG = "com.acooldog.toolbox"


@pytest.fixture()
def service(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield AppReleaseService(session, releases_dir=str(tmp_path / "releases"))
    finally:
        session.close()


def create_release(service, **overrides):
    """创建发布记录并返回**模型对象**（服务的管理侧接口接收模型）。"""
    payload = {
        "packageName": PKG,
        "channel": "stable",
        "versionCode": 20111,
        "versionName": "v1.1",
        "status": "published",
    }
    payload.update(overrides)
    response = service.create_release(CreateAppReleaseRequest(**payload))
    return service.get_release(response.id)


def test_no_release_means_no_update(service):
    result = service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "")
    assert result.update is False
    assert result.versionCode == 0


def test_newer_release_is_offered(service):
    create_release(service, minSupportedVersionCode=20100, sizeBytes=1234, sha256="ab" * 32)
    result = service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "")
    assert result.update is True
    assert result.versionCode == 20111
    assert result.force is False
    assert result.sizeBytes == 1234
    assert result.sha256 == "ab" * 32


def test_same_or_newer_client_gets_no_update(service):
    create_release(service)
    assert service.resolve_version(PKG, "stable", 20111, "arm64-v8a", "").update is False
    assert service.resolve_version(PKG, "stable", 20112, "arm64-v8a", "").update is False


def test_min_supported_forces_update(service):
    create_release(service, minSupportedVersionCode=20120)
    result = service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "")
    assert result.update is True
    assert result.force is True


def test_rollout_blocks_when_zero(service):
    create_release(service, rolloutPercent=0)
    assert service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "device-1").update is False


def test_rollout_allows_when_full(service):
    create_release(service, rolloutPercent=100)
    assert service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "").update is True


def test_rollout_without_install_id_is_conservative(service):
    create_release(service, rolloutPercent=50)
    assert service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "").update is False


def test_rollout_bucketing_is_stable_for_same_install_id(service):
    create_release(service, rolloutPercent=50)
    first = service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "install-xyz").update
    second = service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "install-xyz").update
    assert first == second


def test_forced_update_ignores_rollout(service):
    create_release(service, rolloutPercent=0, force=True)
    result = service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "")
    assert result.update is True
    assert result.force is True


def test_draft_and_revoked_are_not_served(service):
    draft = create_release(service, status="draft")
    assert service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "").update is False

    published = create_release(service, status="published")
    assert service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "").update is True

    service.revoke_release(published)
    assert service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "").update is False
    assert draft.status == "draft"


def test_mirror_urls_round_trip(service):
    create_release(service, mirrorUrls=["https://a.example/x.apk", "", "https://b.example/y.apk"])
    result = service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "")
    assert result.mirrorUrls == ["https://a.example/x.apk", "https://b.example/y.apk"]


def test_save_bundle_computes_size_and_sha256(service):
    content = b"PK\x03\x04fake-apk-bytes"
    uploaded = service.save_bundle("Free Schoolrun v1.1_arm64-v8a_release.apk", content)
    assert uploaded.sizeBytes == len(content)
    assert len(uploaded.sha256) == 64
    assert uploaded.fileName.endswith(".apk")
    assert " " not in uploaded.fileName


def test_save_bundle_sanitizes_path_traversal(service):
    uploaded = service.save_bundle("../../evil.apk", b"x")
    assert "/" not in uploaded.fileName
    assert ".." not in uploaded.fileName


def test_latest_published_picks_highest_version(service):
    create_release(service, versionCode=20111)
    create_release(service, versionCode=20113)
    create_release(service, versionCode=20112)
    assert service.latest_published(PKG, "stable").version_code == 20113


def test_channel_isolation(service):
    create_release(service, channel="stable", versionCode=20111)
    create_release(service, channel="beta", versionCode=20120)
    assert service.resolve_version(PKG, "stable", 20110, "arm64-v8a", "").versionCode == 20111
    assert service.resolve_version(PKG, "beta", 20110, "arm64-v8a", "").versionCode == 20120
