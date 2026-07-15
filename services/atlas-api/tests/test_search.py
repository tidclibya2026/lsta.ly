from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.session import create_database_engine
from app.main import app
from app.services.arabic_text_service import normalize_arabic_text, prepare_search_query, remove_diacritics


@pytest.fixture
def search_client() -> Generator[TestClient, None, None]:
    engine = create_database_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    def override() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_arabic_normalization() -> None:
    assert remove_diacritics("سُليمان") == "سليمان"
    assert normalize_arabic_text("  المَدِينَةُ  القَدِيمَة  ") == "المدينه القديمه"
    assert prepare_search_query("أكادير") == prepare_search_query("اكادير")


def test_exact_national_id_arabic_fulltext_and_ranking(search_client: TestClient) -> None:
    headers = {"X-LSTA-Reviewer-Role": "reviewer"}
    exact = search_client.get(
        "/api/v1/search", params={"q": "LSTA-OLD-TRIPOLI-000001", "source": "all"}, headers=headers
    )
    assert exact.status_code == 200
    assert exact.json()["items"][0]["national_id"] == "LSTA-OLD-TRIPOLI-000001"
    assert exact.json()["items"][0]["relevance_score"] == 100
    arabic = search_client.get("/api/v1/search", params={"q": "المدينة القديمة", "source": "staging"}, headers=headers)
    assert arabic.status_code == 200 and arabic.json()["items"]
    assert all(item["source"] == "staging" for item in arabic.json()["items"])
    assert "query_time_ms" in arabic.json()


def test_autocomplete_facets_pagination_and_visibility(search_client: TestClient) -> None:
    viewer = search_client.get("/api/v1/search", params={"q": "طرابلس", "source": "all"})
    assert viewer.status_code == 200
    assert all(item["source"] == "registry" for item in viewer.json()["items"])
    assert search_client.get("/api/v1/search", params={"q": "طرابلس", "source": "staging"}).status_code == 403
    headers = {"X-LSTA-Reviewer-Role": "reviewer"}
    autocomplete = search_client.get("/api/v1/search/autocomplete", params={"q": "طرابلس", "limit": 5}, headers=headers)
    assert autocomplete.status_code == 200 and len(autocomplete.json()["items"]) <= 5
    assert search_client.get("/api/v1/search/facets", headers=headers).json()["source_counts"]["staging"] == 430
    assert search_client.get("/api/v1/search", params={"q": "طرابلس", "limit": 101}, headers=headers).status_code == 422


def test_empty_radius_bbox_and_validation(search_client: TestClient) -> None:
    headers = {"X-LSTA-Reviewer-Role": "gis_specialist"}
    assert search_client.get("/api/v1/search", headers=headers).json()["items"] == []
    radius = search_client.get(
        "/api/v1/search",
        params={
            "source": "staging",
            "center_lat": 32.8958861,
            "center_lon": 13.1807868,
            "radius_meters": 500,
            "limit": 20,
        },
        headers=headers,
    )
    assert radius.status_code == 200 and radius.json()["items"]
    bbox = search_client.get(
        "/api/v1/search", params={"source": "staging", "bbox": "13.17,32.89,13.19,32.91", "limit": 10}, headers=headers
    )
    assert bbox.status_code == 200 and bbox.json()["items"]
    assert (
        search_client.get(
            "/api/v1/search", params={"center_lat": 32.8, "radius_meters": 200000}, headers=headers
        ).status_code
        == 422
    )
