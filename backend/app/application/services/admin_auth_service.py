from app.core.config import settings


class AdminAuthService:
    def verify_credentials(self, username: str, password: str) -> bool:
        return username == settings.admin_username and password == settings.admin_password
