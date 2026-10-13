from datetime import datetime, timezone

from fastapi import HTTPException, status

from app.application.schemas.auth_schemas import AccountResponse
from app.application.schemas.internal_account_schemas import (
    BanInternalAccountRequest,
    CreateInternalAccountRequest,
    UpdateInternalAccountRequest,
)
from app.core.auth_scope import build_scoped_username, normalize_client_variant
from app.core.config import settings
from app.core.id_generator import generate_public_id
from app.core.security import hash_password
from app.core.tester_account import normalize_account_status, normalize_stored_tester_type, normalize_tester_type, tester_type_label
from app.infrastructure.db.models.auth import AuthAccountModel


class InternalAccountAdminService:
    def __init__(self, db, client_variant: str | None = None):
        self._db = db
        self._variant = normalize_client_variant(client_variant or settings.internal_auth_variant)

    def list_accounts(self) -> list[AccountResponse]:
        rows = (
            self._db.query(AuthAccountModel)
            .filter(AuthAccountModel.client_variant == self._variant)
            .order_by(AuthAccountModel.created_at.desc())
            .all()
        )
        return [self._to_response(row) for row in rows]

    def create_account(self, payload: CreateInternalAccountRequest) -> AccountResponse:
        username = payload.username.strip()
        scoped_username = build_scoped_username(username, self._variant)
        existing = (
            self._db.query(AuthAccountModel)
            .filter(
                AuthAccountModel.username == scoped_username,
                AuthAccountModel.client_variant == self._variant,
            )
            .first()
        )
        if existing is not None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="内部账号已存在。")

        now = self._now_millis()
        account = AuthAccountModel(
            id=generate_public_id("acct"),
            username=scoped_username,
            display_username=username,
            client_variant=self._variant,
            remark=payload.remark.strip(),
            password_hash=hash_password(payload.password),
            tester_type=normalize_tester_type(payload.testerType),
            status="active",
            ban_reason="",
            ban_detail="",
            banned_at=0,
            bound_device_id="",
            bound_device_name="",
            failed_device_attempts=0,
            last_login_at=0,
            created_at=now,
            updated_at=now,
        )
        self._db.add(account)
        self._db.commit()
        self._db.refresh(account)
        return self._to_response(account)

    def update_account(self, account_id: str, payload: UpdateInternalAccountRequest) -> AccountResponse:
        account = self._find_account(account_id)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内部账号不存在。")

        normalized_status = normalize_account_status(payload.status)
        now = self._now_millis()

        account.remark = (payload.remark or "").strip()
        account.tester_type = normalize_tester_type(payload.testerType)
        account.status = normalized_status
        if normalized_status == "banned":
            account.ban_reason = (payload.banReason or "").strip() or account.ban_reason or "manual"
            account.ban_detail = (payload.banDetail or "").strip()
            if not account.banned_at:
                account.banned_at = now
        else:
            account.ban_reason = ""
            account.ban_detail = ""
            account.banned_at = 0
        if payload.password.strip():
            account.password_hash = hash_password(payload.password.strip())
        if payload.resetBoundDevice:
            account.bound_device_id = ""
            account.bound_device_name = ""
            account.failed_device_attempts = 0
        account.updated_at = now
        self._db.commit()
        self._db.refresh(account)
        return self._to_response(account)

    def ban_account(self, account_id: str, payload: BanInternalAccountRequest) -> AccountResponse:
        account = self._find_account(account_id)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内部账号不存在。")

        now = self._now_millis()
        account.status = "banned"
        account.ban_reason = (payload.banReason or "").strip() or "manual"
        account.ban_detail = (payload.banDetail or "").strip()
        account.banned_at = now
        account.updated_at = now
        self._db.commit()
        self._db.refresh(account)
        return self._to_response(account)

    def unban_account(self, account_id: str) -> AccountResponse:
        account = self._find_account(account_id)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内部账号不存在。")

        account.status = "active"
        account.ban_reason = ""
        account.ban_detail = ""
        account.banned_at = 0
        account.updated_at = self._now_millis()
        self._db.commit()
        self._db.refresh(account)
        return self._to_response(account)

    def delete_account(self, account_id: str) -> None:
        account = self._find_account(account_id)
        if account is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内部账号不存在。")
        self._db.delete(account)
        self._db.commit()

    def _find_account(self, account_id: str) -> AuthAccountModel | None:
        return (
            self._db.query(AuthAccountModel)
            .filter(
                AuthAccountModel.id == account_id,
                AuthAccountModel.client_variant == self._variant,
            )
            .first()
        )

    def _to_response(self, account: AuthAccountModel) -> AccountResponse:
        return AccountResponse(
            id=account.id,
            username=account.display_username or account.username,
            clientVariant=account.client_variant or self._variant,
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

    def _now_millis(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
