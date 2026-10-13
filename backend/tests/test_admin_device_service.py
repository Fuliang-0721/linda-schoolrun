import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.services.admin_device_service import AdminDeviceService
from app.core.auth_scope import build_scoped_device_id
from app.core.config import settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import auth as auth_models  # noqa: F401


class AdminDeviceServiceTest(unittest.TestCase):
    AUTH_TABLES = [
        auth_models.AuthAccountModel.__table__,
        auth_models.AuthLoginAttemptModel.__table__,
        auth_models.AuthDeviceModel.__table__,
        auth_models.AuthAlertModel.__table__,
    ]

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)
        Base.metadata.create_all(bind=self.engine, tables=self.AUTH_TABLES)
        session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        self.db = session_factory()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=self.engine, tables=self.AUTH_TABLES)
        self.engine.dispose()

    def test_devices_are_isolated_by_client_variant(self):
        self._insert_device("shared-device", "exclusive", "login-fsr device")
        self._insert_device("shared-device", settings.internal_auth_variant, "linda-xiaopao device")

        login_fsr_devices = AdminDeviceService(self.db, "exclusive")
        toolbox_devices = AdminDeviceService(self.db, settings.internal_auth_variant)

        self.assertEqual([device.deviceName for device in login_fsr_devices.list_devices()], ["login-fsr device"])
        self.assertEqual([device.deviceName for device in toolbox_devices.list_devices()], ["linda-xiaopao device"])

        banned = login_fsr_devices.ban_device("shared-device")
        self.assertEqual(banned.status, "blocked")
        self.assertEqual(banned.clientVariant, "exclusive")

        toolbox_device = toolbox_devices.list_devices()[0]
        self.assertEqual(toolbox_device.status, "active")
        self.assertEqual(toolbox_device.clientVariant, settings.internal_auth_variant)

    def test_wrong_variant_cannot_update_other_domain_device(self):
        self._insert_device("login-only-device", "exclusive", "login-fsr device")

        with self.assertRaises(HTTPException) as wrong_scope:
            AdminDeviceService(self.db, settings.internal_auth_variant).ban_device("login-only-device")

        self.assertEqual(wrong_scope.exception.status_code, 404)

    def _insert_device(self, raw_device_id: str, variant: str, device_name: str) -> None:
        now = int(datetime.now(timezone.utc).timestamp() * 1000)
        self.db.add(
            auth_models.AuthDeviceModel(
                device_id=build_scoped_device_id(raw_device_id, variant),
                raw_device_id=raw_device_id,
                client_variant=variant,
                device_name=device_name,
                status="active",
                ban_reason="",
                ban_detail="",
                banned_until=0,
                wrong_password_count=0,
                wrong_password_window_started_at=0,
                wrong_password_ban_count=0,
                wrong_device_attempt_count=0,
                last_ip="127.0.0.1",
                last_attempt_at=now,
                created_at=now,
                updated_at=now,
            )
        )
        self.db.commit()


if __name__ == "__main__":
    unittest.main()
