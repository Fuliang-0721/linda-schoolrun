from datetime import datetime, timezone

from sqlalchemy import inspect, text

from app.core.auth_scope import (
    build_scoped_device_id,
    build_scoped_username,
    extract_raw_scoped_value,
    extract_scoped_variant,
)
from app.core.config import settings
from app.core.id_generator import generate_public_id
from app.infrastructure.db.coordinate_precision import migrate_coordinate_precision

LEGACY_LOGIN_VARIANT = "exclusive"
SCHEMA_MIGRATION_TABLE = "backend_schema_migrations"
LEGACY_TOOLBOX_TESTER_MIGRATION = "20260430_move_legacy_toolbox_testers_to_donor"
VALID_TESTER_TYPES = {"ordinary", "advanced", "donor", "pioneer"}
DEFAULT_INTERNAL_SOFTWARE_NAMES = ("闪动校园", "体适能", "悦跑运动", "运动世界", "步道乐跑")


def migrate_schema(engine) -> None:
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    with engine.begin() as connection:
        _ensure_schema_migrations_table(connection)
        if "usage_tips" in table_names:
            _migrate_usage_tip_columns(engine, connection)
        if "app_notices" in table_names:
            _migrate_app_notices(inspector, connection)
        if "shared_simulation_configs" in table_names:
            _migrate_shared_simulation_configs(inspector, connection)
        if "auth_accounts" in table_names:
            _migrate_auth_accounts(inspector, connection)
        if "auth_devices" in table_names:
            _migrate_auth_devices(inspector, connection)
        _ensure_internal_software_names(connection)
        if {"auth_accounts", "auth_devices", "auth_login_attempts"}.issubset(table_names):
            _repair_login_fsr_variants(connection)
        if "auth_accounts" in table_names:
            _move_legacy_toolbox_testers_to_donor(connection)
        _ensure_app_releases(connection)
        _ensure_device_logs(connection)
        _ensure_client_telemetry(connection)
        _ensure_access_policy(connection)
        migrate_coordinate_precision(connection)


def _ensure_access_policy(connection) -> None:
    """新表：全局服务开关（单行）。老库用 checkfirst 补建，并补上默认行。"""
    from app.infrastructure.db.models.access_policy import AccessPolicyModel

    AccessPolicyModel.__table__.create(bind=connection, checkfirst=True)
    columns = {column["name"] for column in inspect(connection).get_columns("access_policy")}
    if "scope" not in columns:
        connection.execute(text("ALTER TABLE access_policy ADD COLUMN scope VARCHAR(16) NOT NULL DEFAULT 'all'"))
    sql = "INSERT INTO access_policy (id, service_enabled, message, scope, updated_at) VALUES (1, 1, '', 'all', 0) "
    sql += "ON DUPLICATE KEY UPDATE id = id" if connection.dialect.name == "mysql" else "ON CONFLICT(id) DO NOTHING"
    connection.execute(text(sql))


def _ensure_client_telemetry(connection):
    from app.infrastructure.db.models.client_telemetry import ClientTelemetryModel
    ClientTelemetryModel.__table__.create(bind=connection, checkfirst=True)


def _ensure_device_logs(connection) -> None:
    """新表：客户端上报的运行日志（崩溃现场 / 手动反馈）。老库用 checkfirst 补建。"""
    from app.infrastructure.db.models.device_log import DeviceLogModel

    DeviceLogModel.__table__.create(bind=connection, checkfirst=True)
    if "token_hash" not in {c["name"] for c in inspect(connection).get_columns("device_logs")}:
        connection.execute(text("ALTER TABLE device_logs ADD COLUMN token_hash VARCHAR(64) NOT NULL DEFAULT ''"))


def _ensure_app_releases(connection) -> None:
    """新表：客户端版本发布记录（自动更新用）。老库用 checkfirst 补建 + 补列。"""
    from sqlalchemy import inspect as sa_inspect

    from app.infrastructure.db.models.app_release import AppReleaseModel

    AppReleaseModel.__table__.create(bind=connection, checkfirst=True)

    # 定向发布白名单列（老库升级用；MySQL 的 TEXT 不支持默认值，故用 VARCHAR）
    columns = {column["name"] for column in sa_inspect(connection).get_columns("app_releases")}
    if "target_install_ids" not in columns:
        connection.execute(
            text(
                "ALTER TABLE app_releases "
                "ADD COLUMN target_install_ids VARCHAR(2048) NOT NULL DEFAULT ''"
            )
        )


def _ensure_schema_migrations_table(connection) -> None:
    connection.execute(
        text(
            f"CREATE TABLE IF NOT EXISTS {SCHEMA_MIGRATION_TABLE} ("
            "name VARCHAR(128) PRIMARY KEY, "
            "applied_at BIGINT NOT NULL DEFAULT 0"
            ")"
        )
    )


def _has_schema_migration(connection, name: str) -> bool:
    row = connection.execute(
        text(f"SELECT name FROM {SCHEMA_MIGRATION_TABLE} WHERE name = :name"),
        {"name": name},
    ).first()
    return row is not None


def _mark_schema_migration(connection, name: str) -> None:
    connection.execute(
        text(f"INSERT INTO {SCHEMA_MIGRATION_TABLE} (name, applied_at) VALUES (:name, :applied_at)"),
        {
            "name": name,
            "applied_at": int(datetime.now(timezone.utc).timestamp() * 1000),
        },
    )


def _migrate_usage_tip_columns(engine, connection) -> None:
    if engine.dialect.name.lower() != "mysql":
        return
    connection.execute(text("ALTER TABLE usage_tips MODIFY COLUMN html_content LONGTEXT NOT NULL"))
    connection.execute(text("ALTER TABLE usage_tips MODIFY COLUMN plain_text LONGTEXT NOT NULL"))


def _migrate_app_notices(inspector, connection) -> None:
    return


def _ensure_internal_software_names(connection) -> None:
    connection.execute(
        text(
            """
            CREATE TABLE IF NOT EXISTS internal_software_names (
                id VARCHAR(64) PRIMARY KEY,
                name VARCHAR(128) NOT NULL UNIQUE,
                status VARCHAR(32) NOT NULL DEFAULT 'pending',
                submitter_account_id VARCHAR(64) NOT NULL DEFAULT '',
                submitter_username VARCHAR(64) NOT NULL DEFAULT '',
                submitter_tester_type VARCHAR(32) NOT NULL DEFAULT '',
                reviewed_at BIGINT NOT NULL DEFAULT 0,
                created_at BIGINT NOT NULL,
                updated_at BIGINT NOT NULL
            )
            """
        )
    )
    now = int(datetime.now(timezone.utc).timestamp() * 1000)
    for name in DEFAULT_INTERNAL_SOFTWARE_NAMES:
        existing = connection.execute(
            text("SELECT id FROM internal_software_names WHERE name = :name"),
            {"name": name},
        ).first()
        if existing is not None:
            continue
        connection.execute(
            text(
                """
                INSERT INTO internal_software_names (
                    id, name, status, submitter_account_id, submitter_username,
                    submitter_tester_type, reviewed_at, created_at, updated_at
                ) VALUES (
                    :id, :name, 'approved', '', '系统预置',
                    'system', :now, :now, :now
                )
                """
            ),
            {"id": generate_public_id("soft"), "name": name, "now": now},
        )


def _migrate_shared_simulation_configs(inspector, connection) -> None:
    existing_columns = {column["name"] for column in inspector.get_columns("shared_simulation_configs")}
    if "natural_altitude_variation_enabled" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE shared_simulation_configs "
                "ADD COLUMN natural_altitude_variation_enabled BOOLEAN NOT NULL DEFAULT 0"
            )
        )
    if "altitude_base_meters" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE shared_simulation_configs "
                "ADD COLUMN altitude_base_meters FLOAT NOT NULL DEFAULT 55.0"
            )
        )
    if "altitude_variation_range" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE shared_simulation_configs "
                "ADD COLUMN altitude_variation_range FLOAT NOT NULL DEFAULT 0.0"
            )
        )
    if "altitude_variation_height_centimeters" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE shared_simulation_configs "
                "ADD COLUMN altitude_variation_height_centimeters FLOAT NOT NULL DEFAULT 0.0"
            )
        )
    if "altitude_variation_probability" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE shared_simulation_configs "
                "ADD COLUMN altitude_variation_probability FLOAT NOT NULL DEFAULT 0.0"
            )
        )
    if "uploader_tester" not in existing_columns:
        connection.execute(
            text(
                "ALTER TABLE shared_simulation_configs "
                "ADD COLUMN uploader_tester BOOLEAN NOT NULL DEFAULT 0"
            )
        )


def _migrate_auth_accounts(inspector, connection) -> None:
    existing_columns = {column["name"] for column in inspector.get_columns("auth_accounts")}
    dialect = connection.dialect.name.lower()
    if connection.dialect.name.lower() == "mysql":
        connection.execute(text("ALTER TABLE auth_accounts MODIFY COLUMN username VARCHAR(160) NOT NULL"))
    if "display_username" not in existing_columns:
        connection.execute(text("ALTER TABLE auth_accounts ADD COLUMN display_username VARCHAR(64) NOT NULL DEFAULT ''"))
    if "client_variant" not in existing_columns:
        connection.execute(text("ALTER TABLE auth_accounts ADD COLUMN client_variant VARCHAR(64) NOT NULL DEFAULT ''"))
    if "tester_type" not in existing_columns:
        connection.execute(text("ALTER TABLE auth_accounts ADD COLUMN tester_type VARCHAR(32) NOT NULL DEFAULT 'ordinary'"))
    if "ban_reason" not in existing_columns:
        connection.execute(text("ALTER TABLE auth_accounts ADD COLUMN ban_reason VARCHAR(255) NOT NULL DEFAULT ''"))
    if "ban_detail" not in existing_columns:
        if dialect == "mysql":
            connection.execute(text("ALTER TABLE auth_accounts ADD COLUMN ban_detail TEXT NULL"))
            connection.execute(text("UPDATE auth_accounts SET ban_detail = '' WHERE ban_detail IS NULL"))
            connection.execute(text("ALTER TABLE auth_accounts MODIFY COLUMN ban_detail TEXT NOT NULL"))
        else:
            connection.execute(text("ALTER TABLE auth_accounts ADD COLUMN ban_detail TEXT NOT NULL DEFAULT ''"))
    if "banned_at" not in existing_columns:
        connection.execute(text("ALTER TABLE auth_accounts ADD COLUMN banned_at BIGINT NOT NULL DEFAULT 0"))

    rows = connection.execute(
        text("SELECT id, username, display_username, client_variant, tester_type, status FROM auth_accounts")
    ).mappings().all()
    for row in rows:
        raw_username = row.get("username")
        display_username = (row.get("display_username") or "").strip() or extract_raw_scoped_value(raw_username)
        client_variant = (
            (row.get("client_variant") or "").strip()
            or extract_scoped_variant(raw_username)
            or LEGACY_LOGIN_VARIANT
        )
        scoped_username = build_scoped_username(display_username, client_variant)
        tester_type = (row.get("tester_type") or "").strip().lower()
        if tester_type not in VALID_TESTER_TYPES:
            tester_type = "" if client_variant == settings.internal_auth_variant else "ordinary"
        status = (row.get("status") or "").strip() or "active"
        if status not in {"active", "banned"}:
            status = "active"
        if (
            raw_username != scoped_username
            or row.get("display_username") != display_username
            or row.get("client_variant") != client_variant
            or row.get("tester_type") != tester_type
            or row.get("status") != status
        ):
            connection.execute(
                text(
                    "UPDATE auth_accounts "
                    "SET username = :username, display_username = :display_username, "
                    "client_variant = :client_variant, tester_type = :tester_type, status = :status "
                    "WHERE id = :id"
                ),
                {
                    "id": row["id"],
                    "username": scoped_username,
                    "display_username": display_username,
                    "client_variant": client_variant,
                    "tester_type": tester_type,
                    "status": status,
                },
            )


def _move_legacy_toolbox_testers_to_donor(connection) -> None:
    if _has_schema_migration(connection, LEGACY_TOOLBOX_TESTER_MIGRATION):
        return
    connection.execute(
        text(
            """
            UPDATE auth_accounts
               SET tester_type = 'donor'
             WHERE client_variant = :toolbox_variant
               AND tester_type IN ('', 'ordinary')
            """
        ),
        {"toolbox_variant": settings.internal_auth_variant},
    )
    _mark_schema_migration(connection, LEGACY_TOOLBOX_TESTER_MIGRATION)


def _migrate_auth_devices(inspector, connection) -> None:
    existing_columns = {column["name"] for column in inspector.get_columns("auth_devices")}
    if connection.dialect.name.lower() == "mysql":
        connection.execute(text("ALTER TABLE auth_devices MODIFY COLUMN device_id VARCHAR(384) NOT NULL"))
    if "raw_device_id" not in existing_columns:
        connection.execute(text("ALTER TABLE auth_devices ADD COLUMN raw_device_id VARCHAR(255) NOT NULL DEFAULT ''"))
    if "client_variant" not in existing_columns:
        connection.execute(text("ALTER TABLE auth_devices ADD COLUMN client_variant VARCHAR(64) NOT NULL DEFAULT ''"))

    rows = connection.execute(
        text("SELECT device_id, raw_device_id, client_variant FROM auth_devices")
    ).mappings().all()
    for row in rows:
        raw_device_id = (row.get("raw_device_id") or "").strip() or extract_raw_scoped_value(row.get("device_id"))
        client_variant = (
            (row.get("client_variant") or "").strip()
            or extract_scoped_variant(row.get("device_id"))
            or LEGACY_LOGIN_VARIANT
        )
        scoped_device_id = build_scoped_device_id(raw_device_id, client_variant)
        if (
            row.get("device_id") != scoped_device_id
            or row.get("raw_device_id") != raw_device_id
            or row.get("client_variant") != client_variant
        ):
            connection.execute(
                text(
                    "UPDATE auth_devices "
                    "SET device_id = :device_id, raw_device_id = :raw_device_id, client_variant = :client_variant "
                    "WHERE device_id = :original_device_id"
                ),
                {
                    "original_device_id": row["device_id"],
                    "device_id": scoped_device_id,
                    "raw_device_id": raw_device_id,
                    "client_variant": client_variant,
                },
            )


def _repair_login_fsr_variants(connection) -> None:
    raw_device_ids_to_move = set()

    blank_accounts = connection.execute(
        text(
            """
            SELECT id, username, password_hash, remark, status, updated_at
            FROM auth_accounts
            WHERE client_variant = ''
            """
        )
    ).mappings().all()
    for row in blank_accounts:
        display_username = extract_raw_scoped_value(row.get("username"))
        if not display_username:
            continue
        existing_account = connection.execute(
            text(
                """
                SELECT id
                FROM auth_accounts
                WHERE id <> :account_id
                  AND (
                        display_username = :display_username
                     OR username = :toolbox_username
                     OR username = :legacy_username
                  )
                ORDER BY created_at ASC
                LIMIT 1
                """
            ),
            {
                "account_id": row["id"],
                "display_username": display_username,
                "toolbox_username": build_scoped_username(display_username, settings.internal_auth_variant),
                "legacy_username": build_scoped_username(display_username, LEGACY_LOGIN_VARIANT),
            },
        ).mappings().first()
        if existing_account is not None:
            connection.execute(
                text(
                    """
                    UPDATE auth_accounts
                       SET password_hash = :password_hash,
                           remark = CASE WHEN :remark = '' THEN remark ELSE :remark END,
                           status = :status,
                           updated_at = CASE WHEN updated_at > :updated_at THEN updated_at ELSE :updated_at END
                     WHERE id = :target_id
                    """
                ),
                {
                    "password_hash": row.get("password_hash") or "",
                    "remark": (row.get("remark") or "").strip(),
                    "status": (row.get("status") or "active").strip() or "active",
                    "updated_at": int(row.get("updated_at") or 0),
                    "target_id": existing_account["id"],
                },
            )
            connection.execute(
                text("DELETE FROM auth_accounts WHERE id = :account_id"),
                {"account_id": row["id"]},
            )
            continue

        connection.execute(
            text(
                """
                UPDATE auth_accounts
                   SET client_variant = :legacy_variant,
                       display_username = :display_username,
                       username = :scoped_username
                 WHERE id = :account_id
                """
            ),
            {
                "legacy_variant": LEGACY_LOGIN_VARIANT,
                "display_username": display_username,
                "scoped_username": build_scoped_username(display_username, LEGACY_LOGIN_VARIANT),
                "account_id": row["id"],
            },
        )

    moved_accounts = connection.execute(
        text(
            """
            SELECT DISTINCT a.id, a.display_username, a.bound_device_id, a.bound_device_name, a.remark
            FROM auth_accounts a
            JOIN auth_login_attempts l
              ON l.app_variant = :legacy_variant
             AND l.success = 1
             AND (l.username = a.display_username OR l.username = a.username)
            WHERE a.client_variant = :toolbox_variant
            """
        ),
        {
            "legacy_variant": LEGACY_LOGIN_VARIANT,
            "toolbox_variant": settings.internal_auth_variant,
        },
    ).mappings().all()

    for row in moved_accounts:
        display_username = (row.get("display_username") or "").strip()
        if not display_username:
            continue
        existing_legacy_account = connection.execute(
            text(
                """
                SELECT id
                FROM auth_accounts
                WHERE id <> :account_id
                  AND client_variant = :legacy_variant
                  AND (
                        display_username = :display_username
                     OR username = :scoped_username
                  )
                LIMIT 1
                """
            ),
            {
                "account_id": row["id"],
                "legacy_variant": LEGACY_LOGIN_VARIANT,
                "display_username": display_username,
                "scoped_username": build_scoped_username(display_username, LEGACY_LOGIN_VARIANT),
            },
        ).mappings().first()
        if existing_legacy_account is not None:
            connection.execute(
                text(
                    """
                    UPDATE auth_accounts dst
                    JOIN auth_accounts src ON src.id = :source_id
                       SET dst.bound_device_id = CASE WHEN dst.bound_device_id = '' THEN src.bound_device_id ELSE dst.bound_device_id END,
                           dst.bound_device_name = CASE WHEN dst.bound_device_name = '' THEN src.bound_device_name ELSE dst.bound_device_name END,
                           dst.remark = CASE WHEN dst.remark = '' THEN src.remark ELSE dst.remark END,
                           dst.status = CASE WHEN dst.status = 'banned' THEN dst.status ELSE src.status END
                     WHERE dst.id = :target_id
                    """
                ),
                {
                    "source_id": row["id"],
                    "target_id": existing_legacy_account["id"],
                },
            )
            connection.execute(
                text("DELETE FROM auth_accounts WHERE id = :account_id"),
                {"account_id": row["id"]},
            )
            bound_device_id = (row.get("bound_device_id") or "").strip()
            if bound_device_id:
                raw_device_ids_to_move.add(bound_device_id)
            continue
        connection.execute(
            text(
                """
                UPDATE auth_accounts
                   SET client_variant = :legacy_variant,
                       username = :scoped_username
                 WHERE id = :account_id
                """
            ),
            {
                "legacy_variant": LEGACY_LOGIN_VARIANT,
                "scoped_username": build_scoped_username(display_username, LEGACY_LOGIN_VARIANT),
                "account_id": row["id"],
            },
        )
        bound_device_id = (row.get("bound_device_id") or "").strip()
        if bound_device_id:
            raw_device_ids_to_move.add(bound_device_id)

    attempt_device_ids = connection.execute(
        text(
            """
            SELECT DISTINCT device_id
            FROM auth_login_attempts
            WHERE app_variant = :legacy_variant
            """
        ),
        {"legacy_variant": LEGACY_LOGIN_VARIANT},
    ).scalars().all()
    raw_device_ids_to_move.update((device_id or "").strip() for device_id in attempt_device_ids if device_id)

    for raw_device_id in raw_device_ids_to_move:
        existing_legacy = connection.execute(
            text(
                """
                SELECT device_id
                FROM auth_devices
                WHERE raw_device_id = :raw_device_id AND client_variant = :legacy_variant
                """
            ),
            {
                "raw_device_id": raw_device_id,
                "legacy_variant": LEGACY_LOGIN_VARIANT,
            },
        ).first()
        if existing_legacy is not None:
            connection.execute(
                text(
                    """
                    DELETE FROM auth_devices
                    WHERE raw_device_id = :raw_device_id AND client_variant = :legacy_variant
                    """
                ),
                {
                    "raw_device_id": raw_device_id,
                    "legacy_variant": LEGACY_LOGIN_VARIANT,
                },
            )

        connection.execute(
            text(
                """
                UPDATE auth_devices
                   SET client_variant = :legacy_variant,
                       device_id = :scoped_device_id,
                       status = 'active',
                       ban_reason = '',
                       ban_detail = '',
                       banned_until = 0,
                       wrong_password_count = 0,
                       wrong_password_window_started_at = 0,
                       wrong_password_ban_count = 0,
                       wrong_device_attempt_count = 0
                 WHERE raw_device_id = :raw_device_id
                   AND client_variant = :toolbox_variant
                """
            ),
            {
                "legacy_variant": LEGACY_LOGIN_VARIANT,
                "scoped_device_id": build_scoped_device_id(raw_device_id, LEGACY_LOGIN_VARIANT),
                "raw_device_id": raw_device_id,
                "toolbox_variant": settings.internal_auth_variant,
            },
        )
