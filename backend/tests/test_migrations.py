import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.application.schemas.auth_schemas import AccountResponse
from app.application.schemas.app_log_schemas import SubmitInternalSoftwareNameRequest, UploadAppLogRequest
from app.application.schemas.simulation_config_schemas import SaveSharedSimulationConfigRequest
from app.application.schemas.notice_schemas import UpdateAppNoticeRequest
from app.application.services.app_log_service import AppLogService
from app.application.services.app_notice_service import AppNoticeService
from app.application.services.shared_simulation_config_service import SharedSimulationConfigService
from app.core.auth_scope import build_scoped_username
from app.core.config import settings
from app.infrastructure.db.base import Base
from app.infrastructure.db.migrations import LEGACY_LOGIN_VARIANT, migrate_schema
from app.infrastructure.db.models import app_notice as app_notice_models  # noqa: F401
from app.infrastructure.db.models import app_log as app_log_models  # noqa: F401
from app.infrastructure.db.models import auth as auth_models  # noqa: F401
from app.infrastructure.db.models import simulation_config as simulation_config_models  # noqa: F401


class BackendMigrationTest(unittest.TestCase):
    AUTH_TABLES = [
        auth_models.AuthAccountModel.__table__,
        auth_models.AuthLoginAttemptModel.__table__,
        auth_models.AuthDeviceModel.__table__,
        auth_models.AuthAlertModel.__table__,
    ]

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:", future=True)

    def tearDown(self):
        self.engine.dispose()

    def test_legacy_toolbox_ordinary_accounts_move_to_donor_once(self):
        Base.metadata.create_all(bind=self.engine, tables=self.AUTH_TABLES)
        with self.engine.begin() as connection:
            self._insert_account(connection, "toolbox-ordinary", settings.internal_auth_variant, "ordinary")
            self._insert_account(connection, "toolbox-advanced", settings.internal_auth_variant, "advanced")
            self._insert_account(connection, "login-fsr-ordinary", LEGACY_LOGIN_VARIANT, "ordinary")

        migrate_schema(self.engine)

        with self.engine.begin() as connection:
            rows = dict(
                connection.execute(
                    text("SELECT display_username, tester_type FROM auth_accounts")
                ).all()
            )
            self.assertEqual(rows["toolbox-ordinary"], "donor")
            self.assertEqual(rows["toolbox-advanced"], "advanced")
            self.assertEqual(rows["login-fsr-ordinary"], "ordinary")

            self._insert_account(connection, "new-toolbox-ordinary", settings.internal_auth_variant, "ordinary")

        migrate_schema(self.engine)

        with self.engine.begin() as connection:
            tester_type = connection.execute(
                text("SELECT tester_type FROM auth_accounts WHERE display_username = :username"),
                {"username": "new-toolbox-ordinary"},
            ).scalar_one()
            self.assertEqual(tester_type, "ordinary")

    def test_shared_simulation_config_migrates_and_persists_altitude_base(self):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE shared_simulation_configs (
                        id VARCHAR(64) PRIMARY KEY,
                        name VARCHAR(128) NOT NULL,
                        mode VARCHAR(32) NOT NULL DEFAULT 'speed',
                        speed FLOAT NOT NULL DEFAULT 0.0,
                        cadence FLOAT NOT NULL DEFAULT 0.0,
                        loop_count INTEGER NOT NULL DEFAULT 1,
                        dynamic_intensity_enabled BOOLEAN NOT NULL DEFAULT 0,
                        intensity_variation_range FLOAT NOT NULL DEFAULT 0.0,
                        intensity_variation_frequency FLOAT NOT NULL DEFAULT 0.0,
                        natural_path_variation_enabled BOOLEAN NOT NULL DEFAULT 0,
                        path_variation_amplitude FLOAT NOT NULL DEFAULT 0.0,
                        natural_altitude_variation_enabled BOOLEAN NOT NULL DEFAULT 0,
                        altitude_variation_range FLOAT NOT NULL DEFAULT 0.0,
                        altitude_variation_height_centimeters FLOAT NOT NULL DEFAULT 0.0,
                        altitude_variation_probability FLOAT NOT NULL DEFAULT 0.0,
                        link_ratio_numerator FLOAT NOT NULL DEFAULT 1.0,
                        steps_per_meter FLOAT NOT NULL DEFAULT 1.0,
                        author_name VARCHAR(64) NOT NULL DEFAULT '',
                        created_at BIGINT NOT NULL,
                        updated_at BIGINT NOT NULL
                    )
                    """
                )
            )

        migrate_schema(self.engine)

        columns = {column["name"] for column in inspect(self.engine).get_columns("shared_simulation_configs")}
        self.assertIn("altitude_base_meters", columns)
        self.assertIn("uploader_tester", columns)

        session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        db = session_factory()
        try:
            response = SharedSimulationConfigService(db).create_config(
                SaveSharedSimulationConfigRequest(
                    name="release-altitude",
                    naturalAltitudeVariationEnabled=True,
                    altitudeBaseMeters=62.5,
                    altitudeVariationRange=0.8,
                    altitudeVariationHeightCentimeters=178,
                    altitudeVariationProbability=0.4,
                )
            )
            self.assertEqual(response.altitudeBaseMeters, 62.5)
        finally:
            db.close()

    def test_shared_simulation_config_marks_authenticated_uploader(self):
        Base.metadata.create_all(bind=self.engine, tables=[simulation_config_models.SharedSimulationConfigModel.__table__])
        session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        db = session_factory()
        try:
            service = SharedSimulationConfigService(db)
            response = service.create_config(
                SaveSharedSimulationConfigRequest(name="tester-config"),
                account=self._account("tester", "advanced"),
            )
            self.assertTrue(response.uploaderTester)
        finally:
            db.close()

    def test_app_notice_migrates_and_persists_notice_fields(self):
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE app_notices (
                        id VARCHAR(32) PRIMARY KEY,
                        title VARCHAR(128) NOT NULL DEFAULT '',
                        message TEXT NOT NULL DEFAULT '',
                        qq_group_number VARCHAR(64) NOT NULL DEFAULT '',
                        bilibili_text VARCHAR(255) NOT NULL DEFAULT '',
                        bilibili_url VARCHAR(512) NOT NULL DEFAULT '',
                        updated_at BIGINT NOT NULL
                    )
                    """
                )
            )

        migrate_schema(self.engine)

        columns = {column["name"] for column in inspect(self.engine).get_columns("app_notices")}
        self.assertIn("title", columns)

        session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        db = session_factory()
        try:
            service = AppNoticeService(db)
            notice = service.update_notice(
                UpdateAppNoticeRequest(
                    title="notice",
                    message="message",
                )
            )
            self.assertEqual(notice.title, "notice")
            self.assertEqual(notice.message, "message")
        finally:
            db.close()

    def test_internal_software_names_seed_review_and_log_archive(self):
        migrate_schema(self.engine)

        columns = {column["name"] for column in inspect(self.engine).get_columns("internal_software_names")}
        self.assertIn("name", columns)
        self.assertIn("status", columns)

        session_factory = sessionmaker(bind=self.engine, autoflush=False, autocommit=False)
        db = session_factory()
        try:
            service = AppLogService(db)
            approved = service.list_approved_software_names()
            self.assertIn("闪动校园", [item.name for item in approved])

            submitted = service.submit_software_name(SubmitInternalSoftwareNameRequest(name="内部测试软件"), None)
            self.assertEqual(submitted.status, "pending")
            reviewed = service.approve_software_name(submitted.id)
            self.assertEqual(reviewed.status, "approved")

            old_log_dir = settings.app_logs_dir
            try:
                with TemporaryDirectory() as log_dir:
                    settings.app_logs_dir = log_dir
                    response = service.upload_log(
                        UploadAppLogRequest(softwareName="内部测试软件", contactQq="123456", logText="line1\nline2"),
                        None,
                    )
                    self.assertEqual(response.softwareName, "内部测试软件")
                    self.assertTrue(response.fileName.endswith(".log"))
                    self.assertTrue(list(Path(log_dir).rglob("*.log")))
            finally:
                settings.app_logs_dir = old_log_dir
        finally:
            db.close()

    def _insert_account(self, connection, username: str, variant: str, tester_type: str) -> None:
        connection.execute(
            text(
                """
                INSERT INTO auth_accounts (
                    id, username, display_username, client_variant, remark, password_hash,
                    tester_type, status, ban_reason, ban_detail, banned_at,
                    bound_device_id, bound_device_name, failed_device_attempts,
                    last_login_at, created_at, updated_at
                ) VALUES (
                    :id, :username, :display_username, :client_variant, '', 'hash',
                    :tester_type, 'active', '', '', 0,
                    '', '', 0, 0, 1, 1
                )
                """
            ),
            {
                "id": username,
                "username": build_scoped_username(username, variant),
                "display_username": username,
                "client_variant": variant,
                "tester_type": tester_type,
            },
        )

    def _account(self, username: str, tester_type: str) -> AccountResponse:
        return AccountResponse(
            id=username,
            username=username,
            clientVariant=settings.internal_auth_variant,
            remark="",
            testerType=tester_type,
            testerTypeLabel=tester_type,
            status="active",
            createdAt=1,
            updatedAt=1,
        )


if __name__ == "__main__":
    unittest.main()
