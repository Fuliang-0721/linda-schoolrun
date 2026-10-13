from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.application.schemas.auth_schemas import (
    AccountResponse,
    AuthAlertListResponse,
    AuthAlertResponse,
    AuthLoginRequest,
    AuthLoginResponse,
)
from app.core.auth_scope import (
    build_scoped_device_id,
    build_scoped_username,
    extract_raw_scoped_value,
    normalize_client_variant,
)
from app.core.config import settings
from app.core.id_generator import generate_public_id
from app.core.security import issue_mobile_token, verify_password
from app.core.tester_account import normalize_stored_tester_type, tester_type_label
from app.infrastructure.db.models.auth import (
    AuthAccountModel,
    AuthAlertModel,
    AuthDeviceModel,
    AuthLoginAttemptModel,
)


class MobileAuthService:
    def __init__(self, db):
        self._db = db

    def login(self, payload: AuthLoginRequest, ip_address: str) -> AuthLoginResponse:
        now = self._now_millis()
        variant = normalize_client_variant(payload.appVariant)
        username = payload.username.strip()
        device = self._get_or_create_device(payload.deviceId, payload.deviceName, variant, ip_address, now)
        self._ensure_device_allowed(device, now)

        account = self._find_account_by_username(username, variant)
        if account is None:
            self._handle_wrong_password(device, None, username, payload, variant, ip_address, now, "account_not_found")

        if account.status == "banned":
            self._record_attempt(account, username, payload, variant, ip_address, False, "account_banned", now)
            self._db.commit()
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=account.ban_detail or "账号已被封禁，请联系管理员处理。",
            )

        if not verify_password(payload.password, account.password_hash):
            self._handle_wrong_password(device, account, username, payload, variant, ip_address, now, "wrong_password")

        self._reset_wrong_password_window(device)

        if not account.display_username:
            account.display_username = username
        expected_scoped_username = build_scoped_username(account.display_username or username, variant)
        if not account.client_variant:
            account.client_variant = variant
        if account.client_variant == variant and account.username != expected_scoped_username:
            account.username = expected_scoped_username
        if not account.bound_device_id:
            account.bound_device_id = payload.deviceId.strip()
            account.bound_device_name = payload.deviceName.strip()
            account.failed_device_attempts = 0
            device.wrong_device_attempt_count = 0
        elif account.bound_device_id != payload.deviceId.strip():
            self._handle_wrong_device_attempt(device, account, payload, variant, ip_address, now)

        account.failed_device_attempts = 0
        account.last_login_at = now
        account.updated_at = now
        device.wrong_device_attempt_count = 0
        device.last_ip = ip_address
        device.last_attempt_at = now
        device.updated_at = now
        self._record_attempt(account, username, payload, variant, ip_address, True, "success", now)
        self._db.commit()
        self._db.refresh(account)

        token = issue_mobile_token(
            {
                "accountId": account.id,
                "username": account.display_username or account.username,
                "deviceId": payload.deviceId.strip(),
                "variant": variant,
            }
        )
        return AuthLoginResponse(token=token, account=self._to_response(account))

    def require_active_account(self, account_id: str, variant: str | None = None) -> AccountResponse:
        if not account_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录。")
        normalized_variant = normalize_client_variant(variant)
        account = (
            self._db.query(AuthAccountModel)
            .filter(
                AuthAccountModel.id == account_id,
                AuthAccountModel.client_variant == normalized_variant,
            )
            .first()
        )
        if account is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态已失效，请重新登录。")
        if account.status == "banned":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=account.ban_detail or "账号已被封禁，请联系管理员。",
            )
        if account.status != "active":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="账号状态无效，请重新登录。")
        return self._to_response(account)

    def ensure_device_request_allowed(self, device_id: str, variant: str | None = None) -> None:
        normalized_device_id = (device_id or "").strip()
        if not normalized_device_id:
            return
        normalized_variant = normalize_client_variant(variant)
        device = self._find_device(normalized_device_id, normalized_variant)
        if device is None:
            return
        self._ensure_device_allowed(device, self._now_millis())

    def get_unread_alerts(self, account_id: str, mark_read: bool = True) -> AuthAlertListResponse:
        rows = (
            self._db.query(AuthAlertModel)
            .filter(AuthAlertModel.account_id == account_id, AuthAlertModel.is_read == 0)
            .order_by(AuthAlertModel.created_at.desc())
            .all()
        )
        if mark_read and rows:
            for row in rows:
                row.is_read = 1
            self._db.commit()
        return AuthAlertListResponse(items=[self._to_alert_response(row) for row in rows])

    def _handle_wrong_password(
        self,
        device: AuthDeviceModel,
        account: AuthAccountModel | None,
        username: str,
        payload: AuthLoginRequest,
        variant: str,
        ip_address: str,
        now: int,
        reason: str,
    ) -> None:
        window_seconds = max(settings.auth_wrong_password_window_seconds, 1)
        window_millis = window_seconds * 1000
        if device.wrong_password_window_started_at <= 0 or now - device.wrong_password_window_started_at > window_millis:
            device.wrong_password_window_started_at = now
            device.wrong_password_count = 0

        device.wrong_password_count = (device.wrong_password_count or 0) + 1
        device.last_ip = ip_address
        device.last_attempt_at = now
        device.updated_at = now

        current_reason = reason
        message = "账号或密码错误。"
        if device.wrong_password_count >= settings.auth_wrong_password_max_attempts:
            device.wrong_password_ban_count = (device.wrong_password_ban_count or 0) + 1
            device.wrong_password_count = 0
            device.wrong_password_window_started_at = 0
            if device.wrong_password_ban_count >= 2:
                device.status = "permanent_banned"
                device.ban_reason = "wrong_password_permanent"
                device.ban_detail = "该设备因连续多次输错账号密码，已被永久封禁。"
                current_reason = "wrong_password_permanent_banned"
                message = "该设备因连续多次输错账号密码，已被永久封禁。"
            else:
                device.status = "temporary_banned"
                device.ban_reason = "wrong_password_temporary"
                device.ban_detail = "该设备因短时间内连续输错账号密码，已被封禁 24 小时。"
                device.banned_until = now + (settings.auth_wrong_password_first_ban_seconds * 1000)
                current_reason = "wrong_password_temporary_banned"
                message = "该设备因短时间内连续输错账号密码，已被封禁 24 小时。"

        self._record_attempt(account, username, payload, variant, ip_address, False, current_reason, now)
        self._db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED if current_reason == reason else status.HTTP_403_FORBIDDEN,
            detail=message,
        )

    def _handle_wrong_device_attempt(
        self,
        device: AuthDeviceModel,
        account: AuthAccountModel,
        payload: AuthLoginRequest,
        variant: str,
        ip_address: str,
        now: int,
    ) -> None:
        device.wrong_device_attempt_count = (device.wrong_device_attempt_count or 0) + 1
        device.last_ip = ip_address
        device.last_attempt_at = now
        device.updated_at = now

        account.failed_device_attempts = device.wrong_device_attempt_count
        account.updated_at = now

        self._record_owner_alert(account, payload, ip_address, now)

        reason = "wrong_device"
        remaining = max(0, settings.auth_wrong_device_max_attempts - device.wrong_device_attempt_count)
        message = f"该账号已绑定其他设备，再尝试 {remaining} 次将封禁当前机器。"
        if device.wrong_device_attempt_count >= settings.auth_wrong_device_max_attempts:
            device.status = "blocked"
            device.ban_reason = "wrong_device_attempt"
            device.ban_detail = "当前设备因多次尝试登录他人已绑定账号，已被封禁，请联系管理员解封。"
            device.banned_until = 0
            reason = "wrong_device_machine_banned"
            message = "当前设备因多次尝试登录他人已绑定账号，已被封禁，请联系管理员解封。"

        self._record_attempt(account, account.display_username or account.username, payload, variant, ip_address, False, reason, now)
        self._db.commit()
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=message)

    def _record_owner_alert(
        self,
        account: AuthAccountModel,
        payload: AuthLoginRequest,
        ip_address: str,
        created_at: int,
    ) -> None:
        alert = AuthAlertModel(
            id=generate_public_id("alert"),
            account_id=account.id,
            message=f"有人尝试用你的账号登录，登录 IP 为 {ip_address}",
            ip_address=ip_address,
            device_id=payload.deviceId.strip(),
            device_name=(payload.deviceName or "").strip(),
            is_read=0,
            created_at=created_at,
        )
        self._db.add(alert)

    def _find_account_by_username(self, username: str, variant: str) -> AuthAccountModel | None:
        scoped_username = build_scoped_username(username, variant)
        account = (
            self._db.query(AuthAccountModel)
            .filter(
                AuthAccountModel.username == scoped_username,
                AuthAccountModel.client_variant == variant,
            )
            .first()
        )
        if account is not None:
            return account
        if variant == settings.internal_auth_variant:
            return None
        return (
            self._db.query(AuthAccountModel)
            .filter(
                (AuthAccountModel.display_username == username) | (AuthAccountModel.username == username),
                AuthAccountModel.client_variant.in_([variant, ""]),
            )
            .order_by(AuthAccountModel.updated_at.desc())
            .first()
        )

    def _find_device(self, raw_device_id: str, variant: str) -> AuthDeviceModel | None:
        scoped_device_id = build_scoped_device_id(raw_device_id, variant)
        device = (
            self._db.query(AuthDeviceModel)
            .filter(
                AuthDeviceModel.device_id == scoped_device_id,
                AuthDeviceModel.client_variant == variant,
            )
            .first()
        )
        if device is not None:
            return device
        if variant == settings.internal_auth_variant:
            return None
        return (
            self._db.query(AuthDeviceModel)
            .filter(
                AuthDeviceModel.raw_device_id == raw_device_id,
                AuthDeviceModel.client_variant.in_([variant, ""]),
            )
            .order_by(AuthDeviceModel.updated_at.desc())
            .first()
        )

    def _get_or_create_device(self, device_id: str, device_name: str, variant: str, ip_address: str, now: int) -> AuthDeviceModel:
        normalized_device_id = (device_id or "").strip()
        scoped_device_id = build_scoped_device_id(normalized_device_id, variant)
        device = self._find_device(normalized_device_id, variant)
        if device is None:
            device = AuthDeviceModel(
                device_id=scoped_device_id,
                raw_device_id=normalized_device_id,
                client_variant=variant,
                device_name=(device_name or "").strip(),
                status="active",
                ban_reason="",
                ban_detail="",
                banned_until=0,
                wrong_password_count=0,
                wrong_password_window_started_at=0,
                wrong_password_ban_count=0,
                wrong_device_attempt_count=0,
                last_ip=ip_address,
                last_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
            self._db.add(device)
            self._db.flush()
            return device

        if device_name and device_name.strip():
            device.device_name = device_name.strip()
        device.device_id = scoped_device_id
        device.raw_device_id = normalized_device_id
        device.client_variant = variant
        device.last_ip = ip_address
        device.last_attempt_at = now
        device.updated_at = now
        return device

    def _ensure_device_allowed(self, device: AuthDeviceModel, now: int) -> None:
        if device.status == "temporary_banned":
            if device.banned_until > now:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=device.ban_detail or "当前设备已被临时封禁，请稍后再试。",
                )
            device.status = "active"
            device.ban_reason = ""
            device.ban_detail = ""
            device.banned_until = 0
            device.wrong_password_count = 0
            device.wrong_password_window_started_at = 0
            device.updated_at = now
            self._db.commit()
            return

        if device.status in {"blocked", "permanent_banned"}:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=device.ban_detail or "当前设备已被封禁，请联系管理员解封。",
            )

    def _reset_wrong_password_window(self, device: AuthDeviceModel) -> None:
        device.wrong_password_count = 0
        device.wrong_password_window_started_at = 0

    def _record_attempt(
        self,
        account: AuthAccountModel | None,
        username: str,
        payload: AuthLoginRequest,
        variant: str,
        ip_address: str,
        success: bool,
        reason: str,
        created_at: int,
    ) -> None:
        self._db.add(
            AuthLoginAttemptModel(
                account_id=account.id if account else None,
                username=(username or "").strip(),
                device_id=payload.deviceId.strip(),
                device_name=(payload.deviceName or "").strip(),
                ip_address=ip_address,
                app_variant=variant,
                success=1 if success else 0,
                reason=reason,
                created_at=created_at,
            )
        )

    def _to_response(self, account: AuthAccountModel) -> AccountResponse:
        return AccountResponse(
            id=account.id,
            username=account.display_username or extract_raw_scoped_value(account.username),
            clientVariant=account.client_variant or normalize_client_variant(None),
            remark=account.remark or "",
            testerType=normalize_stored_tester_type(account.tester_type),
            testerTypeLabel=tester_type_label(account.tester_type),
            status=account.status,
            banReason=account.ban_reason or "",
            banDetail=account.ban_detail or "",
            bannedAt=account.banned_at or 0,
            boundDeviceId=account.bound_device_id or "",
            boundDeviceName=account.bound_device_name or "",
            failedDeviceAttempts=account.failed_device_attempts or 0,
            lastLoginAt=account.last_login_at or 0,
            createdAt=account.created_at,
            updatedAt=account.updated_at,
        )

    def _to_alert_response(self, alert: AuthAlertModel) -> AuthAlertResponse:
        return AuthAlertResponse(
            id=alert.id,
            message=alert.message,
            ipAddress=alert.ip_address,
            deviceId=alert.device_id,
            deviceName=alert.device_name,
            createdAt=alert.created_at,
        )

    def _now_millis(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
