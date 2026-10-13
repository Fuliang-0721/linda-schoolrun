"""定向发布（只给内部人员/指定设备）相关的单元测试。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.application.schemas.app_release_schemas import CreateAppReleaseRequest, UpdateAppReleaseRequest
from app.application.services.app_release_service import AppReleaseService
from app.infrastructure.db.base import Base
from app.infrastructure.db.models.app_release import AppReleaseModel  # noqa: F401

PKG = "com.acooldog.toolbox"


def test_public_history_excludes_internal_and_targeted_releases(service):
    create(service, versionCode=20118)
    create(service, versionCode=20119, channel="internal")
    create(service, versionCode=20120, targetInstallIds=["private-install"])
    assert [item.versionCode for item in service.list_history(PKG)] == [20118]


@pytest.fixture()
def service(tmp_path):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, future=True)
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine, future=True)()
    try:
        yield AppReleaseService(session, releases_dir=str(tmp_path / "releases"))
    finally:
        session.close()


def create(service, **overrides):
    payload = {
        "packageName": PKG,
        "channel": "stable",
        "versionCode": 20118,
        "versionName": "v1.8",
        "status": "published",
    }
    payload.update(overrides)
    response = service.create_release(CreateAppReleaseRequest(**payload))
    return service.get_release(response.id)


def test_normal_user_does_not_see_targeted_release(service):
    """普通用户（不在白名单）只能看到 stable 版本，看不到定向发布的内部版本。"""
    create(service, versionCode=20118, versionName="v1.8")  # 公开稳定版
    create(service, channel="internal", versionCode=20119, versionName="v1.9",
           targetInstallIds=["tester-device-1"])  # 只给内部

    normal = service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "normal-user-xyz")
    assert normal.update is True
    assert normal.versionCode == 20118  # 拿到的是公开版，不是 v1.9

    tester = service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "tester-device-1")
    assert tester.update is True
    assert tester.versionCode == 20119  # 白名单命中，即使渠道是 stable
    assert tester.versionName == "v1.9D"  # 内部版本号强制带 D 后缀


def test_targeted_release_ignores_channel(service):
    create(service, versionCode=20118)
    create(service, channel="beta", versionCode=20120, targetInstallIds=["dev-a"])

    assert service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "dev-a").versionCode == 20120
    assert service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "dev-b").versionCode == 20118


def test_internal_account_on_internal_channel(service):
    """客户端按内部登录状态上报 channel=internal 时，能拿到内部版本。"""
    create(service, versionCode=20118)
    create(service, channel="internal", versionCode=20119, versionName="v1.9")

    # 普通用户（stable）看不到 internal 版本
    assert service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "u1").versionCode == 20118
    # 内部人员（internal 渠道）能看到
    assert service.resolve_version(PKG, "internal", 20117, "arm64-v8a", "u2").versionCode == 20119


def test_empty_install_id_never_matches_targeted(service):
    create(service, versionCode=20118)
    create(service, channel="internal", versionCode=20119, targetInstallIds=["only-this-one"])

    # 没带 installId 时不能命中定向发布（避免泄漏给未知设备）
    assert service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "").versionCode == 20118


def test_can_add_and_remove_targets(service):
    release = create(service, channel="internal", versionCode=20119)
    # 未指定白名单时不影响下发（内部实现可能存 "" 或 "[]"）
    assert service._parse_targets(release.target_install_ids) == []

    service.update_release(release, UpdateAppReleaseRequest(targetInstallIds=["a", "b"]))
    assert service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "a").versionCode == 20119

    # 清空白名单后立刻停止下发
    service.update_release(release, UpdateAppReleaseRequest(targetInstallIds=[]))
    assert service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "a").update is False


def test_targeted_release_respects_rollout(service):
    """定向发布同样受灰度控制：rolloutPercent=0 时不下发，调回 100 后立即下发。"""
    release = create(service, channel="internal", versionCode=20119, rolloutPercent=0,
                     targetInstallIds=["tester-1"])
    assert service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "tester-1").update is False

    service.update_release(release, UpdateAppReleaseRequest(rolloutPercent=100))
    assert service.resolve_version(PKG, "stable", 20117, "arm64-v8a", "tester-1").update is True


def test_internal_version_name_gets_d_suffix(service):
    """内部版本号强制带 D，公开版本号不带。"""
    stable = create(service, versionCode=20130, versionName="v1.12", channel="stable")
    assert stable.version_name == "v1.12"

    internal = create(service, versionCode=20131, versionName="v1.12", channel="internal")
    assert internal.version_name == "v1.12D"

    # 定向发布（渠道是 stable 但带白名单）同样算内部版本
    targeted = create(service, versionCode=20132, versionName="v1.12", channel="stable",
                      targetInstallIds=["dev-1"])
    assert targeted.version_name == "v1.12D"

    # 手误多写一个 D 也不会变成 DD
    again = create(service, versionCode=20133, versionName="v1.12D", channel="internal")
    assert again.version_name == "v1.12D"

    # 公开版本会去掉结尾的 D
    public = create(service, versionCode=20134, versionName="v1.12D", channel="stable")
    assert public.version_name == "v1.12"


def test_clearing_whitelist_drops_d_suffix(service):
    """内部版本转为公开（清空白名单）后自动去掉 D。"""
    release = create(service, versionCode=20140, versionName="v1.13", channel="stable",
                     targetInstallIds=["dev-1"])
    assert release.version_name == "v1.13D"

    updated = service.update_release(release, UpdateAppReleaseRequest(targetInstallIds=[]))
    assert updated.versionName == "v1.13"  # update_release 返回响应对象
