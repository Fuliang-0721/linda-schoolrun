import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from app.core.download_tokens import authorize_url

from app.application.schemas.app_release_schemas import (
    AppReleaseHistoryItem,
    AppReleaseResponse,
    AppVersionResponse,
    CreateAppReleaseRequest,
    UpdateAppReleaseRequest,
    UploadedBundleResponse,
)
from app.core.config import settings
from app.core.id_generator import generate_public_id
from app.infrastructure.db.models.app_release import AppReleaseModel

VALID_STATUSES = {"draft", "published", "revoked"}
_SAFE_FILE_NAME = re.compile(r"[^A-Za-z0-9._-]+")


class AppReleaseService:
    """版本发布与自动更新检查。

    - 公开侧：resolve_version() 决定某个客户端是否需要更新（含强制与灰度）
    - 管理侧：草稿/发布/撤销/删除 + APK 上传
    """

    def __init__(self, db, releases_dir: str | None = None):
        self._db = db
        self._releases_dir = Path(releases_dir or settings.releases_dir)

    # ------------------------------------------------------------------ 公开侧
    def resolve_version(
        self,
        package_name: str,
        channel: str,
        current_version_code: int,
        abi: str,
        install_id: str,
        allow_targeted: bool = True,
    ) -> AppVersionResponse:
        release = self._pick_release(package_name, channel, install_id, current_version_code, abi, allow_targeted)
        if release is None:
            self._log_check(package_name, channel, current_version_code, install_id, None)
            return AppVersionResponse(update=False, channel=channel, packageName=package_name)

        base = {
            "channel": channel,
            "packageName": package_name,
            "versionCode": release.version_code,
            "versionName": release.version_name,
            "minSupportedVersionCode": release.min_supported_version_code,
            "rolloutPercent": release.rollout_percent,
            "sizeBytes": release.size_bytes,
            "sha256": release.sha256,
            "downloadUrl": authorize_url(release.download_url),
            "mirrorUrls": [authorize_url(url) for url in self._parse_mirrors(release.mirror_urls)],
            "changelog": release.changelog,
            "releaseNotesUrl": release.release_notes_url,
            "abi": release.abi,
            "publishedAt": release.published_at,
        }

        if current_version_code <= 0 or release.version_code <= current_version_code:
            self._log_check(package_name, channel, current_version_code, install_id, None)
            return AppVersionResponse(update=False, **base)

        forced = bool(
            release.force_update
            or (
                release.min_supported_version_code > 0
                and current_version_code < release.min_supported_version_code
            )
        )
        if not forced and not self._in_rollout(release, install_id):
            self._log_check(package_name, channel, current_version_code, install_id, None)
            return AppVersionResponse(update=False, **base)

        self._log_check(package_name, channel, current_version_code, install_id, release)
        return AppVersionResponse(update=True, force=forced, **base)

    def latest_published(self, package_name: str, channel: str) -> AppReleaseModel | None:
        return (
            self._db.query(AppReleaseModel)
            .filter(
                AppReleaseModel.package_name == package_name.strip(),
                AppReleaseModel.channel == channel.strip(),
                AppReleaseModel.status == "published",
            )
            .order_by(AppReleaseModel.version_code.desc())
            .first()
        )

    def list_history(self, package_name: str, limit: int = 30) -> list[AppReleaseHistoryItem]:
        """公开的更新记录：已发布版本按版本号倒序（用于客户端「更新记录」页面）。"""
        safe_limit = max(1, min(int(limit), 100))
        rows = (
            self._db.query(AppReleaseModel)
            .filter(
                AppReleaseModel.package_name == package_name.strip(),
                AppReleaseModel.status == "published",
                AppReleaseModel.channel == "stable",
                AppReleaseModel.target_install_ids.in_(["", "[]"]),
            )
            .order_by(AppReleaseModel.version_code.desc())
            .limit(safe_limit)
            .all()
        )
        return [
            AppReleaseHistoryItem(
                versionCode=row.version_code,
                versionName=row.version_name,
                channel=row.channel,
                publishedAt=row.published_at,
                changelog=row.changelog,
            )
            for row in rows
        ]

    @staticmethod
    def _normalize_version_name(version_name: str, channel: str, targets: list[str]) -> str:
        """内部版本号一律带 D 后缀，公开版本号不带（规则由服务端强制，避免手误）。

        - channel=internal 或带定向白名单 → 内部版本 → 结尾补 "D"
        - 其它（stable 且无白名单）→ 公开版本 → 去掉结尾的 "D"
        """
        name = (version_name or "").strip()
        is_internal = (channel or "").strip().lower() == "internal" or bool(targets)
        if is_internal:
            if not name.upper().endswith("D"):
                name += "D"
            return name
        if name.upper().endswith("D"):
            return name[:-1]
        return name

    def _pick_release(
        self,
        package_name: str,
        channel: str,
        install_id: str,
        current_version_code: int = 0, abi: str = "", allow_targeted: bool = True,
    ) -> AppReleaseModel | None:
        """按「渠道匹配」或「定向白名单命中」挑选要给该客户端的最高版本。

        - 定向发布（target_install_ids 非空）：只发给名单内的 installId，**忽略渠道**
          → 用于只更新内部人员，普通用户完全看不到
        - 普通发布：按 channel 匹配（stable 给所有用户，internal 只给内部人员）
        """
        rows = (
            self._db.query(AppReleaseModel)
            .filter(
                AppReleaseModel.package_name == package_name.strip(),
                AppReleaseModel.status == "published",
            )
            .all()
        )

        normalized_install_id = (install_id or "").strip()
        eligible: list[AppReleaseModel] = []
        for row in rows:
            if abi and row.abi and row.abi != abi:
                continue
            forced = row.force_update or (row.min_supported_version_code > 0 and current_version_code < row.min_supported_version_code)
            if not forced and not self._in_rollout(row, install_id):
                continue
            targets = self._parse_targets(row.target_install_ids)
            if targets:
                if allow_targeted and normalized_install_id and normalized_install_id in targets:
                    eligible.append(row)
                continue
            if row.channel == channel.strip():
                eligible.append(row)

        if not eligible:
            return None
        return max(eligible, key=lambda item: item.version_code)

    def _parse_targets(self, raw: str) -> list[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item).strip() for item in parsed if str(item).strip()]

    def _log_check(
        self,
        package_name: str,
        channel: str,
        current_version_code: int,
        install_id: str,
        release: AppReleaseModel | None,
    ) -> None:
        """记录每次版本检查：既便于排查，也用于发现测试机的 installId。"""
        try:
            log_dir = Path(settings.app_logs_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            path = log_dir / "version_check.log"
            if path.exists() and path.stat().st_size > 2 * 1024 * 1024:
                path.unlink()
            line = "%s package=%s channel=%s current=%s installId=%s update=%s offer=%s(%s)\n" % (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                package_name,
                channel,
                current_version_code,
                (install_id or "").strip() or "-",
                "1" if release is not None else "0",
                release.version_name if release is not None else "-",
                release.version_code if release is not None else 0,
            )
            with path.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except Exception:
            # 日志失败不能影响版本检查
            pass

    def _in_rollout(self, release: AppReleaseModel, install_id: str) -> bool:
        percent = max(0, min(100, int(release.rollout_percent)))
        if percent >= 100:
            return True
        if percent <= 0:
            return False
        # 没有 installId 时保守处理（灰度阶段不下发）；强制更新不受此限制
        if not install_id.strip():
            return False
        digest = hashlib.sha256(f"{release.id}:{install_id.strip()}".encode("utf-8")).hexdigest()
        return int(digest[:8], 16) % 100 < percent

    # ------------------------------------------------------------------ 管理侧
    def list_releases(self, package_name: str | None = None, channel: str | None = None) -> list[AppReleaseResponse]:
        query = self._db.query(AppReleaseModel)
        if package_name:
            query = query.filter(AppReleaseModel.package_name == package_name.strip())
        if channel:
            query = query.filter(AppReleaseModel.channel == channel.strip())
        rows = query.order_by(
            AppReleaseModel.channel.asc(),
            AppReleaseModel.version_code.desc(),
        ).all()
        return [self._to_response(row) for row in rows]

    def get_release(self, release_id: str) -> AppReleaseModel | None:
        return self._db.query(AppReleaseModel).filter(AppReleaseModel.id == release_id).first()

    def create_release(self, payload: CreateAppReleaseRequest) -> AppReleaseResponse:
        now = self._now_millis()
        target_list = [item.strip() for item in payload.targetInstallIds if item.strip()]
        targets_json = json.dumps(target_list, ensure_ascii=False)

        release = AppReleaseModel(
            id=generate_public_id("rel"),
            package_name=payload.packageName.strip(),
            channel=payload.channel.strip(),
            version_code=payload.versionCode,
            version_name=self._normalize_version_name(
                payload.versionName, payload.channel, target_list
            ),
            min_supported_version_code=payload.minSupportedVersionCode,
            force_update=payload.force,
            rollout_percent=payload.rolloutPercent,
            size_bytes=payload.sizeBytes,
            sha256=payload.sha256.strip().lower(),
            download_url=payload.downloadUrl.strip(),
            mirror_urls=json.dumps([item.strip() for item in payload.mirrorUrls if item.strip()], ensure_ascii=False),
            changelog=payload.changelog,
            release_notes_url=payload.releaseNotesUrl.strip(),
            abi=payload.abi.strip(),
            target_install_ids=targets_json,
            status=payload.status,
            published_at=now if payload.status == "published" else 0,
            created_at=now,
            updated_at=now,
        )
        self._db.add(release)
        self._db.commit()
        self._db.refresh(release)
        return self._to_response(release)

    def update_release(self, release: AppReleaseModel, payload: UpdateAppReleaseRequest) -> AppReleaseResponse:
        if payload.versionName is not None:
            release.version_name = payload.versionName.strip()
        if payload.minSupportedVersionCode is not None:
            release.min_supported_version_code = payload.minSupportedVersionCode
        if payload.force is not None:
            release.force_update = payload.force
        if payload.rolloutPercent is not None:
            release.rollout_percent = payload.rolloutPercent
        if payload.sizeBytes is not None:
            release.size_bytes = payload.sizeBytes
        if payload.sha256 is not None:
            release.sha256 = payload.sha256.strip().lower()
        if payload.downloadUrl is not None:
            release.download_url = payload.downloadUrl.strip()
        if payload.mirrorUrls is not None:
            release.mirror_urls = json.dumps(
                [item.strip() for item in payload.mirrorUrls if item.strip()], ensure_ascii=False
            )
        if payload.changelog is not None:
            release.changelog = payload.changelog
        if payload.releaseNotesUrl is not None:
            release.release_notes_url = payload.releaseNotesUrl.strip()
        if payload.abi is not None:
            release.abi = payload.abi.strip()
        if payload.targetInstallIds is not None:
            release.target_install_ids = json.dumps(
                [item.strip() for item in payload.targetInstallIds if item.strip()], ensure_ascii=False
            )
        if payload.status is not None:
            self._apply_status(release, payload.status)
        # 版本号命名规则：内部版本带 D 后缀，公开版本不带
        release.version_name = self._normalize_version_name(
            release.version_name,
            release.channel,
            self._parse_targets(release.target_install_ids),
        )
        release.updated_at = self._now_millis()
        self._db.commit()
        self._db.refresh(release)
        return self._to_response(release)

    def publish_release(self, release: AppReleaseModel) -> AppReleaseResponse:
        self._apply_status(release, "published")
        release.updated_at = self._now_millis()
        self._db.commit()
        self._db.refresh(release)
        return self._to_response(release)

    def revoke_release(self, release: AppReleaseModel) -> AppReleaseResponse:
        self._apply_status(release, "revoked")
        release.updated_at = self._now_millis()
        self._db.commit()
        self._db.refresh(release)
        return self._to_response(release)

    def delete_release(self, release: AppReleaseModel) -> None:
        self._db.delete(release)
        self._db.commit()

    def _apply_status(self, release: AppReleaseModel, status_value: str) -> None:
        status = status_value.strip().lower()
        if status not in VALID_STATUSES:
            raise ValueError("非法的发布状态：" + status_value)
        release.status = status
        if status == "published":
            release.published_at = release.published_at or self._now_millis()

    # ------------------------------------------------------------------ APK 上传
    def save_bundle(self, file_name: str, content: bytes) -> UploadedBundleResponse:
        from io import BytesIO
        return self.save_bundle_stream(file_name, BytesIO(content))

    def save_bundle_stream(self, file_name, stream, max_bytes=400 * 1024 * 1024):
        import os
        import tempfile
        from fastapi import HTTPException
        self._releases_dir.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(prefix=".upload-", dir=self._releases_dir)
        total = 0
        digest = hashlib.sha256()
        try:
            with os.fdopen(fd, "wb") as output:
                while chunk := stream.read(1024 * 1024):
                    total += len(chunk)
                    if total > max_bytes:
                        raise HTTPException(413, "安装包过大")
                    digest.update(chunk)
                    output.write(chunk)
                output.flush()
                os.fsync(output.fileno())
            if not total:
                raise HTTPException(400, "上传内容为空")
            sha = digest.hexdigest()
            safe_name = sha + ".apk"
            target = self._releases_dir / safe_name
            if not target.exists():
                os.replace(name, target)
            base = settings.release_public_base_url.strip().rstrip("/")
            return UploadedBundleResponse(fileName=safe_name, sizeBytes=total, sha256=sha,
                                          downloadUrl=f"{base}/{safe_name}" if base else safe_name)
        finally:
            Path(name).unlink(missing_ok=True)

    def _sanitize_file_name(self, file_name: str) -> str:
        raw = (file_name or "").strip().replace("\\", "/").split("/")[-1]
        cleaned = _SAFE_FILE_NAME.sub("-", raw).strip("-.")
        if not cleaned:
            cleaned = "bundle.apk"
        if not cleaned.lower().endswith(".apk"):
            cleaned = cleaned + ".apk"
        return cleaned

    # ------------------------------------------------------------------ 工具
    def _parse_mirrors(self, raw: str) -> list[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
        except (ValueError, TypeError):
            return []
        if not isinstance(parsed, list):
            return []
        return [str(item).strip() for item in parsed if str(item).strip()]

    def _to_response(self, release: AppReleaseModel) -> AppReleaseResponse:
        return AppReleaseResponse(
            id=release.id,
            packageName=release.package_name,
            channel=release.channel,
            versionCode=release.version_code,
            versionName=release.version_name,
            minSupportedVersionCode=release.min_supported_version_code,
            force=release.force_update,
            rolloutPercent=release.rollout_percent,
            sizeBytes=release.size_bytes,
            sha256=release.sha256,
            downloadUrl=release.download_url,
            mirrorUrls=self._parse_mirrors(release.mirror_urls),
            changelog=release.changelog,
            releaseNotesUrl=release.release_notes_url,
            abi=release.abi,
            status=release.status,
            targetInstallIds=self._parse_targets(release.target_install_ids),
            publishedAt=release.published_at,
            createdAt=release.created_at,
            updatedAt=release.updated_at,
        )

    def _now_millis(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
