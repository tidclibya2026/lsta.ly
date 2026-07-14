from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_database_engine, session_factory

engine = create_database_engine(get_settings().database_url)
SessionLocal = session_factory(engine)


def get_db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session
