from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from order_service.config import get_settings


class Base(DeclarativeBase):
    """Các bảng của order_db. Đổi schema qua Alembic:
    alembic revision --autogenerate -m "..." && alembic upgrade head."""


engine = create_engine(get_settings().database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: mỗi request một session."""
    with SessionLocal() as session:
        yield session
