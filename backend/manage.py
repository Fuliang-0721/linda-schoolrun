from app.infrastructure.db.base import Base
from app.infrastructure.db.session import engine
from app.infrastructure.db.models import nfc as nfc_models  # noqa: F401
from app.infrastructure.db.models import route as route_models  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


if __name__ == "__main__":
    init_db()
    print("Database tables are ready.")
