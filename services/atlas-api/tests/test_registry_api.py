from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.session import create_database_engine
from app.main import app
from app.models import AuditLog, Site, SiteDocument, SiteProfile, SiteVersion
from app.services.site_completeness_service import calculate_site_completeness


@pytest.fixture
def registry() -> Generator[tuple[TestClient, Session, Site], None, None]:
    engine = create_database_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    site = session.scalar(select(Site).order_by(Site.national_id))
    assert site is not None

    def override() -> Generator[Session, None, None]:
        yield session

    app.dependency_overrides[get_db] = override
    try:
        yield TestClient(app), session, site
    finally:
        app.dependency_overrides.clear()
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_registry_list_details_pagination_and_filters(registry: tuple[TestClient, Session, Site]) -> None:
    client, _, site = registry
    page = client.get("/api/v1/registry/sites", params={"limit": 1, "verification_status": site.verification_status})
    assert page.status_code == 200
    assert page.json()["total"] == registry[1].scalar(select(func.count()).select_from(Site).where(Site.verification_status == site.verification_status))
    assert page.json()["items"][0]["national_id"] == site.national_id
    details = client.get(f"/api/v1/registry/sites/{site.national_id}")
    assert details.status_code == 200
    assert details.json()["geometry"] is not None
    assert client.get("/api/v1/registry/sites/INVALID-ID").status_code == 404


def test_profile_permissions_version_and_audit(registry: tuple[TestClient, Session, Site]) -> None:
    client, session, site = registry
    profile = session.scalar(select(SiteProfile).where(SiteProfile.site_id == site.id))
    assert profile is not None
    profile.internal_notes = "سري"
    session.flush()
    viewer = client.get(f"/api/v1/registry/sites/{site.national_id}/profile")
    assert "internal_notes" not in viewer.json()
    before_versions = session.scalar(
        select(func.count()).select_from(SiteVersion).where(SiteVersion.site_id == site.id)
    )
    response = client.put(
        f"/api/v1/registry/sites/{site.national_id}/profile",
        json={"short_description_ar": "وصف تجريبي", "internal_notes": "يجب تجاهله"},
        headers={"X-LSTA-Reviewer-Role": "editor"},
    )
    assert response.status_code == 200
    assert "internal_notes" not in response.json()
    assert (
        session.scalar(select(func.count()).select_from(SiteVersion).where(SiteVersion.site_id == site.id))
        == before_versions + 1
    )
    assert (
        session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.entity_id == site.id, AuditLog.action == "site_profile_updated")
        )
        >= 1
    )


def test_attribute_document_and_completeness(registry: tuple[TestClient, Session, Site]) -> None:
    client, session, site = registry
    attribute = client.put(
        f"/api/v1/registry/sites/{site.national_id}/attributes/heritage_period",
        json={"attribute_group": "heritage", "label_ar": "الفترة", "value_text": "عثمانية"},
        headers={"X-LSTA-Reviewer-Role": "editor"},
    )
    assert attribute.status_code == 200
    document = client.post(
        f"/api/v1/registry/sites/{site.national_id}/documents",
        json={"document_type": "reference", "title_ar": "مرجع", "file_name": "reference.pdf"},
        headers={"X-LSTA-Reviewer-Role": "editor"},
    )
    assert document.status_code == 200
    assert session.scalar(select(func.count()).select_from(SiteDocument).where(SiteDocument.site_id == site.id)) >= 1
    result = calculate_site_completeness(session, site)
    assert 0 <= result["score"] <= 100
    assert sum(item["weight"] for item in result["breakdown"].values()) == 100
