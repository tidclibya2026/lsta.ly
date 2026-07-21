"""Isolated database guard and shared transactional fixtures for Atlas API tests."""
import os
from collections.abc import Generator

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

TEST_URL = os.getenv("LSTA_TEST_DATABASE_URL", "")


def _assert_isolated_test_database(database_url: str) -> None:
    if not database_url:
        raise RuntimeError("LSTA_TEST_DATABASE_URL is required for pytest")
    database = make_url(database_url).database
    if database != "lsta_test":
        raise RuntimeError(
            "Refusing pytest: LSTA_TEST_DATABASE_URL must target the isolated lsta_test database"
        )


_assert_isolated_test_database(TEST_URL)
os.environ["DATABASE_URL"] = TEST_URL

from app.core.config import get_settings  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402
from tests.seed_test_database import reset_and_seed_test_database  # noqa: E402

get_settings.cache_clear()


@pytest.fixture(scope="session", autouse=True)
def seeded_test_database() -> Generator[None, None, None]:
    engine = create_database_engine(TEST_URL)
    reset_and_seed_test_database(engine, TEST_URL)
    yield
    engine.dispose()


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    engine = create_database_engine(TEST_URL)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()
