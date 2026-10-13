import sys
import unittest
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.schemas.auth_schemas import AuthLoginRequest
from app.application.schemas.internal_account_schemas import (
    BanInternalAccountRequest,
    CreateInternalAccountRequest,
    UpdateInternalAccountRequest,
)
from app.application.services.internal_account_admin_service import InternalAccountAdminService
from app.application.services.mobile_auth_service import MobileAuthService
from app.core.config import settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import auth as auth_models  # noqa: F401
from app.infrastructure.db.models import tip as tip_models  # noqa: F401


class InternalAccountAdminServiceTest(unittest.TestCase):
    AUTH_TABLES = [
        auth_models.AuthAccountModel.__table__,
        auth_models.AuthLoginAttemptModel.__table__,
        auth_models.AuthDeviceModel.__table__,
        auth_models.AuthAlertModel.__table__,
    ]

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine, tables=self.AUTH_TABLES)
        self._create_usage_tips_stub()
        session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = session_factory()
        self.admin_service = InternalAccountAdminService(self.db)
        self.mobile_service = MobileAuthService(self.db)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine, tables=self.AUTH_TABLES)
        self.engine.dispose()

    def _create_usage_tips_stub(self):
        with self.engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE usage_tips (
                    id VARCHAR(64) PRIMARY KEY,
                    title VARCHAR(255) NOT NULL DEFAULT '',
                    html_content TEXT NOT NULL DEFAULT '',
                    plain_text TEXT NOT NULL DEFAULT '',
                    contributor_qq VARCHAR(64) NOT NULL DEFAULT '',
                    is_published INTEGER NOT NULL DEFAULT 1,
                    author_account_id VARCHAR(64) NOT NULL DEFAULT '',
                    author_username VARCHAR(64) NOT NULL DEFAULT '',
                    created_at BIGINT NOT NULL DEFAULT 0,
                    updated_at BIGINT NOT NULL DEFAULT 0
                )
                """
            )

    def test_tester_account_lifecycle(self):
        created = self.admin_service.create_account(
            CreateInternalAccountRequest(
                username="tester01",
                password="secret",
                remark="first wave",
                testerType="pioneer",
            )
        )
        self.assertEqual(created.testerType, "pioneer")
        self.assertEqual(created.testerTypeLabel, "先锋测试账号")
        self.assertEqual(created.status, "active")

        updated = self.admin_service.update_account(
            created.id,
            UpdateInternalAccountRequest(
                remark="donor group",
                testerType="donor",
                status="active",
            ),
        )
        self.assertEqual(updated.testerType, "donor")
        self.assertEqual(updated.testerTypeLabel, "贡献者账号")

        banned = self.admin_service.ban_account(
            created.id,
            BanInternalAccountRequest(
                banReason="policy",
                banDetail="测试资格暂停",
            ),
        )
        self.assertEqual(banned.status, "banned")
        self.assertEqual(banned.banReason, "policy")
        self.assertGreater(banned.bannedAt, 0)

        with self.assertRaises(HTTPException) as banned_login:
            self.mobile_service.login(
                AuthLoginRequest(
                    username="tester01",
                    password="secret",
                    deviceId="device-1",
                    appVariant=settings.internal_auth_variant,
                ),
                "127.0.0.1",
            )
        self.assertEqual(banned_login.exception.status_code, 403)

        unbanned = self.admin_service.unban_account(created.id)
        self.assertEqual(unbanned.status, "active")
        self.assertEqual(unbanned.banReason, "")
        self.assertEqual(unbanned.bannedAt, 0)

        login = self.mobile_service.login(
            AuthLoginRequest(
                username="tester01",
                password="secret",
                deviceId="device-1",
                appVariant=settings.internal_auth_variant,
            ),
            "127.0.0.1",
        )
        self.assertEqual(login.account.id, created.id)

        self.admin_service.delete_account(created.id)
        self.assertEqual(self.admin_service.list_accounts(), [])

    def test_accounts_are_isolated_by_client_variant(self):
        login_fsr_admin = InternalAccountAdminService(self.db, "exclusive")
        toolbox_admin = InternalAccountAdminService(self.db, settings.internal_auth_variant)

        login_account = login_fsr_admin.create_account(
            CreateInternalAccountRequest(
                username="shared-tester",
                password="login-secret",
                remark="login-fsr account",
                testerType="ordinary",
            )
        )
        toolbox_account = toolbox_admin.create_account(
            CreateInternalAccountRequest(
                username="shared-tester",
                password="toolbox-secret",
                remark="linda-xiaopao account",
                testerType="advanced",
            )
        )

        self.assertNotEqual(login_account.id, toolbox_account.id)
        self.assertEqual(login_account.clientVariant, "exclusive")
        self.assertEqual(toolbox_account.clientVariant, settings.internal_auth_variant)
        self.assertEqual([account.id for account in login_fsr_admin.list_accounts()], [login_account.id])
        self.assertEqual([account.id for account in toolbox_admin.list_accounts()], [toolbox_account.id])

        with self.assertRaises(HTTPException) as wrong_scope:
            toolbox_admin.ban_account(
                login_account.id,
                BanInternalAccountRequest(banReason="scope-check", banDetail=""),
            )
        self.assertEqual(wrong_scope.exception.status_code, 404)

        login = self.mobile_service.login(
            AuthLoginRequest(
                username="shared-tester",
                password="login-secret",
                deviceId="login-device",
                appVariant="exclusive",
            ),
            "127.0.0.1",
        )
        toolbox = self.mobile_service.login(
            AuthLoginRequest(
                username="shared-tester",
                password="toolbox-secret",
                deviceId="toolbox-device",
                appVariant=settings.internal_auth_variant,
            ),
            "127.0.0.1",
        )

        self.assertEqual(login.account.id, login_account.id)
        self.assertEqual(toolbox.account.id, toolbox_account.id)


if __name__ == "__main__":
    unittest.main()
