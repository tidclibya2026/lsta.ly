"""Isolated database guard and shared transactional fixtures for Atlas API tests."""
import os
from collections.abc import Generator
from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

TEST_URL = os.getenv("LSTA_TEST_DATABASE_URL", "")
if "test" not in TEST_URL.lower() or TEST_URL.rsplit("/", 1)[-1].split("?", 1)[0] == "lsta":
    raise RuntimeError("Refusing pytest: LSTA_TEST_DATABASE_URL must target an isolated test database (for example lsta_test)")
os.environ["DATABASE_URL"] = TEST_URL

from app.core.config import get_settings  # noqa: E402
from app.db.session import create_database_engine  # noqa: E402
from app.models import Site  # noqa: E402

get_settings.cache_clear()

@pytest.fixture(scope="session", autouse=True)
def seed_minimal_reference_data() -> Generator[None, None, None]:
    engine=create_database_engine(TEST_URL)
    with Session(engine) as s:
        if not s.scalar(select(func.count()).select_from(Site)):
            s.add(Site(id=uuid4(),national_id="LSTA-TEST-000001",name_ar="موقع اختبار",verification_status="draft"));s.commit()
    yield
    engine.dispose()

@pytest.fixture
def db_session() -> Generator[Session,None,None]:
    engine=create_database_engine(TEST_URL);connection=engine.connect();transaction=connection.begin();session=Session(bind=connection,expire_on_commit=False)
    try:yield session
    finally:session.close();transaction.rollback();connection.close();engine.dispose()
