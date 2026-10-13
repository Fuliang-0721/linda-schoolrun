from datetime import datetime, timedelta, timezone
from pathlib import Path
import re

from fastapi import HTTPException, status

from app.application.schemas.app_log_schemas import (
    InternalSoftwareNameResponse,
    SubmitInternalSoftwareNameRequest,
    UploadAppLogRequest,
    UploadAppLogResponse,
)
from app.application.schemas.auth_schemas import AccountResponse
from app.core.config import settings
from app.core.id_generator import generate_public_id
from app.infrastructure.db.models.app_log import InternalSoftwareNameModel

DEFAULT_INTERNAL_SOFTWARE_NAMES = ("闪动校园", "体适能", "悦跑运动", "运动世界", "步道乐跑")
APPROVED_STATUS = "approved"
PENDING_STATUS = "pending"
REJECTED_STATUS = "rejected"
SUBMISSION_TIMEZONE = timezone(timedelta(hours=8))


class AppLogService:
    def __init__(self, db):
        self._db = db

    def list_approved_software_names(self) -> list[InternalSoftwareNameResponse]:
        self._ensure_default_names()
        rows = (
            self._db.query(InternalSoftwareNameModel)
            .filter(InternalSoftwareNameModel.status == APPROVED_STATUS)
            .order_by(InternalSoftwareNameModel.created_at.asc(), InternalSoftwareNameModel.name.asc())
            .all()
        )
        return [self._to_response(row) for row in rows]

    def list_admin_software_names(self) -> list[InternalSoftwareNameResponse]:
        self._ensure_default_names()
        rows = (
            self._db.query(InternalSoftwareNameModel)
            .order_by(InternalSoftwareNameModel.status.asc(), InternalSoftwareNameModel.updated_at.desc())
            .all()
        )
        return [self._to_response(row) for row in rows]

    def submit_software_name(
            self,
            payload: SubmitInternalSoftwareNameRequest,
            account: AccountResponse | None,
    ) -> InternalSoftwareNameResponse:
        name = self._normalize_name(payload.name)
        row = self._find_by_name(name)
        now = self._now_millis()
        if row is None:
            row = InternalSoftwareNameModel(
                id=generate_public_id("soft"),
                name=name,
                status=PENDING_STATUS,
                submitter_account_id=account.id if account else "",
                submitter_username=account.username if account else "未登录",
                submitter_tester_type=account.testerType if account else "anonymous",
                reviewed_at=0,
                created_at=now,
                updated_at=now,
            )
            self._db.add(row)
        elif row.status != APPROVED_STATUS:
            row.status = PENDING_STATUS
            row.submitter_account_id = account.id if account else ""
            row.submitter_username = account.username if account else "未登录"
            row.submitter_tester_type = account.testerType if account else "anonymous"
            row.reviewed_at = 0
            row.updated_at = now
        self._db.commit()
        self._db.refresh(row)
        return self._to_response(row)

    def create_approved_software_name(self, payload: SubmitInternalSoftwareNameRequest) -> InternalSoftwareNameResponse:
        name = self._normalize_name(payload.name)
        row = self._find_by_name(name)
        now = self._now_millis()
        if row is None:
            row = InternalSoftwareNameModel(
                id=generate_public_id("soft"),
                name=name,
                status=APPROVED_STATUS,
                submitter_account_id="",
                submitter_username="管理员",
                submitter_tester_type="admin",
                reviewed_at=now,
                created_at=now,
                updated_at=now,
            )
            self._db.add(row)
        else:
            row.status = APPROVED_STATUS
            row.reviewed_at = now
            row.updated_at = now
        self._db.commit()
        self._db.refresh(row)
        return self._to_response(row)

    def approve_software_name(self, name_id: str) -> InternalSoftwareNameResponse:
        row = self._find_by_id(name_id)
        now = self._now_millis()
        row.status = APPROVED_STATUS
        row.reviewed_at = now
        row.updated_at = now
        self._db.commit()
        self._db.refresh(row)
        return self._to_response(row)

    def reject_software_name(self, name_id: str) -> InternalSoftwareNameResponse:
        row = self._find_by_id(name_id)
        now = self._now_millis()
        row.status = REJECTED_STATUS
        row.reviewed_at = now
        row.updated_at = now
        self._db.commit()
        self._db.refresh(row)
        return self._to_response(row)

    def delete_software_name(self, name_id: str) -> None:
        row = self._find_by_id(name_id)
        self._db.delete(row)
        self._db.commit()

    def upload_log(
            self,
            payload: UploadAppLogRequest,
            account: AccountResponse | None,
    ) -> UploadAppLogResponse:
        software_name = self._normalize_name(payload.softwareName)
        contact_qq = self._normalize_contact_qq(payload.contactQq)
        log_text = payload.logText.strip()
        row = self._find_by_name(software_name)
        if row is None or row.status != APPROVED_STATUS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择已审核通过的内部软件名。")

        now = datetime.now(SUBMISSION_TIMEZONE)
        date_folder = now.strftime("%Y-%m-%d")
        accurate_date = now.strftime("%Y-%m-%d_%H-%M-%S-%f")[:-3]
        tester_type = self._account_tester_type(account)
        username = account.username if account else "未登录"
        file_name = self._safe_path_part(f"【{tester_type}】【{username}】【{contact_qq}】【{accurate_date}】.log")
        target_dir = self._log_root_dir() / self._safe_path_part(software_name) / date_folder
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = self._dedupe_path(target_dir / file_name)
        header = f"【{tester_type}】【{username}】【{contact_qq}】【{accurate_date}】"
        target_file.write_text(
            header
            + "\n内部软件："
            + software_name
            + "\n提交时间："
            + now.isoformat()
            + "\n\n"
            + log_text
            + "\n",
            encoding="utf-8",
        )
        return UploadAppLogResponse(message="日志已上传。", softwareName=software_name, fileName=target_file.name)

    def _ensure_default_names(self) -> None:
        now = self._now_millis()
        changed = False
        for name in DEFAULT_INTERNAL_SOFTWARE_NAMES:
            if self._find_by_name(name) is not None:
                continue
            self._db.add(
                InternalSoftwareNameModel(
                    id=generate_public_id("soft"),
                    name=name,
                    status=APPROVED_STATUS,
                    submitter_account_id="",
                    submitter_username="系统预置",
                    submitter_tester_type="system",
                    reviewed_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            changed = True
        if changed:
            self._db.commit()

    def _find_by_name(self, name: str) -> InternalSoftwareNameModel | None:
        return self._db.query(InternalSoftwareNameModel).filter(InternalSoftwareNameModel.name == name).first()

    def _find_by_id(self, name_id: str) -> InternalSoftwareNameModel:
        row = self._db.query(InternalSoftwareNameModel).filter(InternalSoftwareNameModel.id == name_id).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="内部软件名不存在。")
        return row

    def _to_response(self, row: InternalSoftwareNameModel) -> InternalSoftwareNameResponse:
        return InternalSoftwareNameResponse(
            id=row.id,
            name=row.name,
            status=row.status,
            submitterUsername=row.submitter_username,
            submitterTesterType=row.submitter_tester_type,
            reviewedAt=row.reviewed_at,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )

    def _normalize_name(self, value: str) -> str:
        normalized = re.sub(r"\s+", " ", (value or "").strip())
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请输入内部软件名。")
        return normalized[:128]

    def _normalize_contact_qq(self, value: str) -> str:
        normalized = (value or "").strip()
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请填写联系QQ。")
        if not re.fullmatch(r"[0-9A-Za-z_-]{4,64}", normalized):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="联系QQ格式不正确。")
        return normalized

    def _account_tester_type(self, account: AccountResponse | None) -> str:
        if account is None:
            return "未登录"
        return account.testerTypeLabel or account.testerType or "测试账号"

    def _log_root_dir(self) -> Path:
        path = Path(settings.app_logs_dir)
        if not path.is_absolute():
            path = Path.cwd() / path
        return path

    def _safe_path_part(self, value: str) -> str:
        safe = re.sub(r'[\\/:*?"<>|\r\n\t]', "_", value.strip())
        return safe[:180] or "unknown"

    def _dedupe_path(self, path: Path) -> Path:
        if not path.exists():
            return path
        stem = path.stem
        suffix = path.suffix
        for index in range(1, 1000):
            candidate = path.with_name(f"{stem}-{index}{suffix}")
            if not candidate.exists():
                return candidate
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="日志文件命名冲突过多。")

    def _now_millis(self) -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1000)
