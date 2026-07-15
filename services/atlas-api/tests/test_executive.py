from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.session import create_database_engine
from app.main import app
from app.services.coverage_gap_service import coverage_by_geometry_type, generate_gap_score
from app.services.executive_alert_service import create_alert
from app.services.executive_kpi_service import calculate_all_kpis
from app.services.executive_snapshot_service import generate_snapshot, validate_snapshot_integrity
from app.services.service_health_service import check_service_health


@pytest.fixture
def executive_session() -> Generator[Session, None, None]:
    engine = create_database_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_real_kpi_calculations(executive_session: Session) -> None:
    values = calculate_all_kpis(executive_session)
    assert values["DATA_TOTAL_STAGING"] == 430
    assert values["DATA_TOTAL_REGISTRY"] == 1
    assert values["DATA_PROMOTION_RATE"] == 0.23
    assert values["MEDIA_PENDING_REVIEW"] == 380
    assert values["DATA_INVALID_GEOMETRY"] == 0


def test_alert_deduplication_and_snapshot(executive_session: Session) -> None:
    first = create_alert(executive_session, "TEST-ALERT", "quality", "warning", "اختبار", "اختبار")
    second = create_alert(executive_session, "TEST-ALERT", "quality", "warning", "اختبار", "اختبار")
    assert first.id == second.id
    snapshot = generate_snapshot(executive_session, "daily", "test")
    assert validate_snapshot_integrity(snapshot)["valid"] is True


def test_coverage_gap_and_health(executive_session: Session) -> None:
    assert coverage_by_geometry_type(executive_session) == {"LineString": 285, "Point": 135, "Polygon": 10}
    assert 0 <= generate_gap_score({"quality": 50, "pending_rate": 80}) <= 100
    health = check_service_health(executive_session)
    assert len(health) == 10
    assert next(item for item in health if item["service_code"] == "postgis")["status"] == "healthy"


def test_role_visibility(executive_session: Session) -> None:
    def override() -> Generator[Session, None, None]:
        yield executive_session

    app.dependency_overrides[get_db] = override
    try:
        client = TestClient(app)
        viewer = client.get("/api/v1/executive/summary")
        assert viewer.status_code == 200 and viewer.json()["limited"] is True
        assert client.get("/api/v1/executive/service-health").status_code == 403
        admin = client.get(
            "/api/v1/executive/service-health", headers={"X-LSTA-Reviewer-Role": "system_admin"}
        )
        assert admin.status_code == 200
        assert all("details" not in item for item in admin.json()["items"])
    finally:
        app.dependency_overrides.clear()
