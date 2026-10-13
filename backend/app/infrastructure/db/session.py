from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# 本地开发（DATABASE_URL=sqlite:///...）与生产（MySQL）共用一个入口。
_engine_options: dict = {"echo": settings.sql_echo, "future": True}
if settings.database_url.startswith("sqlite"):
    # FastAPI 的同步端点跑在线程池里，SQLite 需要放开线程检查
    _engine_options["connect_args"] = {"check_same_thread": False}
else:
    _engine_options["pool_pre_ping"] = True
    _engine_options["pool_recycle"] = 3600

engine = create_engine(settings.database_url, **_engine_options)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, class_=Session)


def get_db_session() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
