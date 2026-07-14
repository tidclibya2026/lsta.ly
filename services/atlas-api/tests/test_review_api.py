from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.session import create_database_engine
from app.main import app
from app.models import ImportFeature, PromotionRecord
from app.services.data_quality_service import QUALITY_WEIGHTS, calculate_quality


@pytest.fixture
def api() -> Generator[tuple[TestClient, Session, ImportFeature], None, None]:
    engine = create_database_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    promoted = select(PromotionRecord.import_feature_id)
    feature = session.scalar(
        select(ImportFeature)
        .where(
            ImportFeature.geometry_type == "Point",
            ImportFeature.missing_name.is_(False),
            ImportFeature.id.not_in(promoted),
        )
        .order_by(ImportFeature.source_feature_id)
    )
    assert feature is not None

    def override_db() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override_db
    try:
        yield TestClient(app), session, feature
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_summary_and_server_side_pagination(api: tuple[TestClient, Session, ImportFeature]) -> None:
    client, _, _ = api
    summary = client.get("/api/v1/review/summary")
    assert summary.status_code == 200
    assert summary.json()["total_features"] == 430
    page = client.get("/api/v1/review/features")
    assert page.status_code == 200
    assert len(page.json()["items"]) == 25
    assert page.json()["total"] == 430


def test_filter_details_quality_and_duplicates(api: tuple[TestClient, Session, ImportFeature]) -> None:
    client, session, feature = api
    filtered = client.get("/api/v1/review/features", params={"geometry_type": "Point", "limit": 5})
    assert filtered.status_code == 200
    assert all(item["geometry_type"] == "Point" for item in filtered.json()["items"])
    with_images = client.get("/api/v1/review/features", params={"has_images": True, "limit": 5})
    assert with_images.status_code == 200
    assert all(item["image_count"] > 0 for item in with_images.json()["items"])
    details = client.get(f"/api/v1/review/features/{feature.id}")
    assert details.status_code == 200
    body = details.json()
    assert body["geometry"]["type"] == "Point"
    assert "quality_breakdown" in body["quality"]
    assert sum(QUALITY_WEIGHTS.values()) == 100
    assert 0 <= calculate_quality(session, feature)["quality_score"] <= 100
    duplicates = client.get(f"/api/v1/review/features/{feature.id}/duplicate-candidates")
    assert duplicates.status_code == 200
    assert isinstance(duplicates.json()["items"], list)


def test_roles_and_successful_review(api: tuple[TestClient, Session, ImportFeature]) -> None:
    client, _, feature = api
    payload = {
        "review_stage": "technical",
        "decision": "needs_correction",
        "reviewer_role": "viewer",
        "notes": "اختبار",
    }
    assert client.post(f"/api/v1/review/features/{feature.id}/reviews", json=payload).status_code == 403
    payload.update({"review_stage": "gis", "decision": "accepted", "reviewer_role": "reviewer"})
    assert (
        client.post(
            f"/api/v1/review/features/{feature.id}/reviews", json=payload, headers={"X-LSTA-Reviewer-Role": "reviewer"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            f"/api/v1/review/features/{feature.id}/reviews", json=payload, headers={"X-LSTA-Reviewer-Role": "unknown"}
        ).status_code
        == 400
    )
    payload.update({"review_stage": "technical", "decision": "needs_correction", "reviewer_role": "editor"})
    response = client.post(
        f"/api/v1/review/features/{feature.id}/reviews", json=payload, headers={"X-LSTA-Reviewer-Role": "editor"}
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "needs_correction"
