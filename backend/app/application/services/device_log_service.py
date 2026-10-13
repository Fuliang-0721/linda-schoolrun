import time

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.application.schemas.device_log_schemas import (
    DeviceLogDetailResponse,
    DeviceLogSummaryResponse,
    UploadDeviceLogRequest,
    UploadDeviceLogResponse,
)
from app.core.exceptions import ResourceNotFoundError
from app.core.id_generator import generate_public_id
from app.infrastructure.db.models.device_log import DeviceLogModel

# 单条日志最大入库体积（超出只保留末尾，末尾才是崩溃现场）
MAX_LOG_BYTES = 400_000
# 库里最多保留多少条日志（超出按时间从旧到新清理）
MAX_KEPT_LOGS = 500


def _now_millis() -> int:
    return int(time.time() * 1000)


class DeviceLogService:
    def __init__(self, db: Session):
        self._db = db

    # ------------------------------------------------------------------ 客户端上传
    def upload(self, payload: UploadDeviceLogRequest, client_ip: str = "") -> UploadDeviceLogResponse:
        from app.core.request_guard import limiter
        import hashlib
        limiter.check(("log-install", payload.installId), 5, 3600)
        text = payload.logText
        encoded = text.encode("utf-8")
        if len(encoded) > MAX_LOG_BYTES:
            # 保留末尾（崩溃现场/最新日志在尾部）
            text = encoded[-MAX_LOG_BYTES:].decode("utf-8", "ignore")

        log = DeviceLogModel(
            id=generate_public_id("log"),
            install_id=payload.installId.strip(),
            token_hash=hashlib.sha256(payload.token.encode()).hexdigest(),
            app_version_name=payload.versionName.strip(),
            app_version_code=payload.versionCode,
            device_model=payload.deviceModel.strip(),
            android_sdk=payload.androidSdk,
            reason=(payload.reason.strip() or "manual")[:32],
            log_text=text,
            size_bytes=len(text.encode("utf-8")),
            client_ip=client_ip,
            created_at=_now_millis(),
        )
        self._db.add(log)
        self._db.commit()
        self._db.refresh(log)
        self._prune()
        return UploadDeviceLogResponse(
            id=log.id,
            sizeBytes=log.size_bytes,
            message="日志已收到，感谢反馈",
        )

    # ------------------------------------------------------------------ 后台查询
    def list_logs(
        self,
        page: int = 1,
        page_size: int = 20,
        install_id: str = "",
        reason: str = "",
        keyword: str = "",
    ) -> tuple[list[DeviceLogSummaryResponse], int]:
        query = self._db.query(DeviceLogModel)
        if install_id.strip():
            query = query.filter(DeviceLogModel.install_id.like(f"%{install_id.strip()}%"))
        if reason.strip():
            query = query.filter(DeviceLogModel.reason == reason.strip())
        if keyword.strip():
            pattern = f"%{keyword.strip()}%"
            query = query.filter(
                DeviceLogModel.log_text.like(pattern)
                | DeviceLogModel.device_model.like(pattern)
                | DeviceLogModel.app_version_name.like(pattern)
            )

        total = query.count()
        safe_page = max(1, page)
        safe_size = max(1, min(page_size, 100))
        rows = (
            query.order_by(DeviceLogModel.created_at.desc())
            .offset((safe_page - 1) * safe_size)
            .limit(safe_size)
            .all()
        )
        return [self._to_summary(row) for row in rows], total

    def get_log(self, log_id: str) -> DeviceLogDetailResponse:
        row = self._db.query(DeviceLogModel).filter(DeviceLogModel.id == log_id).first()
        if row is None:
            raise ResourceNotFoundError(f"日志 '{log_id}' 不存在")
        summary = self._to_summary(row)
        return DeviceLogDetailResponse(**summary.model_dump(), logText=row.log_text)

    def delete_log(self, log_id: str) -> bool:
        row = self._db.query(DeviceLogModel).filter(DeviceLogModel.id == log_id).first()
        if row is None:
            raise ResourceNotFoundError(f"日志 '{log_id}' 不存在")
        self._db.delete(row)
        self._db.commit()
        return True

    def stats(self) -> dict:
        total = self._db.query(func.count(DeviceLogModel.id)).scalar() or 0
        crash = (
            self._db.query(func.count(DeviceLogModel.id))
            .filter(DeviceLogModel.reason == "crash")
            .scalar()
            or 0
        )
        total_bytes = self._db.query(func.coalesce(func.sum(DeviceLogModel.size_bytes), 0)).scalar() or 0
        return {"total": int(total), "crash": int(crash), "totalBytes": int(total_bytes)}

    # ------------------------------------------------------------------ 内部
    def _to_summary(self, row: DeviceLogModel) -> DeviceLogSummaryResponse:
        return DeviceLogSummaryResponse(
            id=row.id,
            installId=row.install_id,
            versionName=row.app_version_name,
            versionCode=row.app_version_code,
            deviceModel=row.device_model,
            androidSdk=row.android_sdk,
            reason=row.reason,
            sizeBytes=row.size_bytes,
            createdAt=row.created_at,
        )

    def _prune(self, keep: int = MAX_KEPT_LOGS) -> None:
        try:
            stale = (
                self._db.query(DeviceLogModel.id)
                .order_by(DeviceLogModel.created_at.desc())
                .offset(keep)
                .limit(200)
                .all()
            )
            if not stale:
                return
            ids = [row[0] for row in stale]
            self._db.query(DeviceLogModel).filter(DeviceLogModel.id.in_(ids)).delete(
                synchronize_session=False
            )
            self._db.commit()
        except Exception:
            # 清理失败不影响上传
            self._db.rollback()
