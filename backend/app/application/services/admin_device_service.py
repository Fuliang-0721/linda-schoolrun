from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.application.schemas.auth_schemas import AuthDeviceResponse, UpdateAuthDeviceRequest
from app.core.auth_scope import build_scoped_device_id, normalize_client_variant
from app.core.config import settings
from app.infrastructure.db.models.auth import AuthDeviceModel


class AdminDeviceService:
    def __init__(self, db, client_variant: str | None = None):
        self._db = db
        self._variant = normalize_client_variant(client_variant or settings.internal_auth_variant)

    def list_devices(self, query: str = "", status_filter: str = "all") -> list[AuthDeviceResponse]:
        statement = self._db.query(AuthDeviceModel).filter(AuthDeviceModel.client_variant == self._variant)
        normalized_query = (query or "").strip()
        if normalized_query:
            like_query = f"%{normalized_query}%"
            statement = statement.filter(
                (AuthDeviceModel.raw_device_id.like(like_query))
                | (AuthDeviceModel.device_name.like(like_query))
                | (AuthDeviceModel.last_ip.like(like_query))
                | (AuthDeviceModel.ban_reason.like(like_query))
                | (AuthDeviceModel.ban_detail.like(like_query))
            )

        normalized_status = (status_filter or "all").strip().lower()
        if normalized_status != "all":
            statement = statement.filter(AuthDeviceModel.status == normalized_status)

        rows = statement.order_by(AuthDeviceModel.updated_at.desc()).all()
        return [self._to_response(row) for row in rows]

    def update_device(self, device_id: str, payload: UpdateAuthDeviceRequest) -> AuthDeviceResponse:
        row = self._find_device(device_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="设备机器码不存在。")

        normalized_status = (payload.status or "active").strip().lower()
        if normalized_status not in {"active", "temporary_banned", "permanent_banned", "blocked"}:
            normalized_status = "active"

        row.device_name = (payload.deviceName or row.device_name or "").strip()
        row.status = normalized_status
        row.ban_reason = "" if normalized_status == "active" else (payload.banReason or "").strip()
        row.ban_detail = "" if normalized_status == "active" else (payload.banDetail or "").strip()
        row.banned_until = 0 if normalized_status != "temporary_banned" else max(0, int(payload.bannedUntil or 0))

        if payload.resetCounters or normalized_status == "active":
            row.wrong_password_count = 0
            row.wrong_password_window_started_at = 0
            row.wrong_device_attempt_count = 0
            if normalized_status == "active":
                row.wrong_password_ban_count = 0

        row.updated_at = self._now_millis()
        self._db.commit()
        self._db.refresh(row)
        return self._to_response(row)

    def ban_device(self, device_id: str) -> AuthDeviceResponse:
        payload = UpdateAuthDeviceRequest(
            status="blocked",
            banReason="manual_ban",
            banDetail="该设备已被管理员手动封禁。",
            bannedUntil=0,
            resetCounters=False,
        )
        return self.update_device(device_id, payload)

    def unban_device(self, device_id: str) -> AuthDeviceResponse:
        payload = UpdateAuthDeviceRequest(
            status="active",
            banReason="",
            banDetail="",
            bannedUntil=0,
            resetCounters=True,
        )
        return self.update_device(device_id, payload)

    def _find_device(self, raw_device_id: str) -> AuthDeviceModel | None:
        scoped_device_id = build_scoped_device_id(raw_device_id, self._variant)
        return (
            self._db.query(AuthDeviceModel)
            .filter(
                AuthDeviceModel.device_id == scoped_device_id,
                AuthDeviceModel.client_variant == self._variant,
            )
            .first()
        )

    def _to_response(self, row: AuthDeviceModel) -> AuthDeviceResponse:
        return AuthDeviceResponse(
            deviceId=row.raw_device_id or row.device_id,
            clientVariant=row.client_variant or self._variant,
            deviceName=row.device_name or "",
            status=row.status,
            banReason=row.ban_reason or "",
            banDetail=row.ban_detail or "",
            bannedUntil=row.banned_until or 0,
            wrongPasswordCount=row.wrong_password_count or 0,
            wrongPasswordBanCount=row.wrong_password_ban_count or 0,
            wrongDeviceAttemptCount=row.wrong_device_attempt_count or 0,
            lastIp=row.last_ip or "",
            lastAttemptAt=row.last_attempt_at or 0,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )

    def _now_millis(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
