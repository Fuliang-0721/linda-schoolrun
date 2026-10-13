from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "SchoolRun Shared Backend"
    app_env: str = "development"
    app_version: str = "1.0.0"
    api_v1_prefix: str = "/api"
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    auto_create_tables: bool = True
    sql_echo: bool = False
    # 可选：用 DATABASE_URL 直接覆盖数据库连接（本地开发可指向 SQLite：sqlite:///./dev.db）
    database_url_override: str = Field(default="", alias="DATABASE_URL")

    cors_allow_origins_raw: str = Field(default="", alias="CORS_ALLOW_ORIGINS")

    mysql_host: str = "127.0.0.1"
    mysql_port: int = 3306
    mysql_database: str = "schoolrun_shared"
    mysql_user: str = "schoolrun_app"
    mysql_password: str = "change_me"
    mysql_charset: str = "utf8mb4"

    admin_username: str = "admin"
    admin_password: str = "change_me_admin"
    admin_session_secret: str = "change_me_session_secret"
    admin_baidu_maps_ak: str = ""
    admin_public_origin: str = ""
    mobile_auth_secret: str = "change_me_mobile_auth_secret"
    mobile_auth_max_age_seconds: int = 60 * 60 * 24 * 30
    internal_auth_variant: str = "schoolrun_toolbox"
    auth_wrong_password_window_seconds: int = 10 * 60
    auth_wrong_password_max_attempts: int = 5
    auth_wrong_password_first_ban_seconds: int = 24 * 60 * 60
    auth_wrong_device_max_attempts: int = 3
    client_notice_title: str = "使用说明"
    client_notice_message: str = "本软件为开源软件，仅供学习交流，禁止盈利。"
    client_notice_group_number: str = ""
    client_bilibili_text: str = "本软件由 Fuliang_teaseller 维护。"
    client_bilibili_url: str = ""
    # 远程关闭：true 时所有客户端启动即被拦截（客户端缓存 3 天）
    client_kill_switch: bool = False
    client_kill_switch_message: str = ""
    app_logs_dir: str = "app_logs"
    # 自动更新：安装包存放目录与对外下载前缀（生产环境交给 Nginx 静态托管）
    releases_dir: str = "releases"
    release_public_base_url: str = ""

    def validate_security(self):
        if self.app_env.lower() != "production":
            return
        for name in ("admin_password", "admin_session_secret", "mobile_auth_secret"):
            value = getattr(self, name)
            if len(value) < (16 if name == "admin_password" else 32) or "change_me" in value or "改成" in value:
                raise RuntimeError(f"Production requires a strong non-example {name}")
        if self.admin_session_secret == self.mobile_auth_secret:
            raise RuntimeError("Session and mobile token secrets must be different")
        if "*" in self.cors_allow_origins:
            raise RuntimeError("Wildcard CORS is forbidden in production")

    @property
    def cors_allow_origins(self) -> list[str]:
        if self.cors_allow_origins_raw.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_allow_origins_raw.split(",") if item.strip()]

    @property
    def database_url(self) -> str:
        # 本地开发可用 DATABASE_URL 覆盖（例如 sqlite:///./dev.db）；留空则走 MySQL
        if self.database_url_override.strip():
            return self.database_url_override.strip()
        return (
            f"mysql+pymysql://{self.mysql_user}:{self.mysql_password}"
            f"@{self.mysql_host}:{self.mysql_port}/{self.mysql_database}"
            f"?charset={self.mysql_charset}"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
