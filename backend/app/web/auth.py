from fastapi import HTTPException, Request, status

from app.core.config import settings

ADMIN_SESSION_KEY = "admin_username"


def is_admin_authenticated(request: Request) -> bool:
    return request.session.get(ADMIN_SESSION_KEY) == settings.admin_username


def require_admin_session(request: Request) -> str:
    username = request.session.get(ADMIN_SESSION_KEY)
    if username != settings.admin_username:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未登录或登录已失效")
    return username
