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


def test_site_version_list_detail_and_comparison_api(
    registry: tuple[TestClient, Session, Site],
) -> None:
    client, session, site = registry

    current_max = session.scalar(
        select(func.max(SiteVersion.version_number)).where(
            SiteVersion.site_id == site.id
        )
    )
    first_number = int(current_max or 0) + 1
    second_number = first_number + 1

    first_version = SiteVersion(
        site_id=site.id,
        version_number=first_number,
        snapshot={
            "site": {
                "name_ar": "لبدة",
                "verification_status": "draft",
            }
        },
        change_summary="نسخة اختبار أولى",
    )
    second_version = SiteVersion(
        site_id=site.id,
        version_number=second_number,
        snapshot={
            "site": {
                "name_ar": "لبدة الكبرى",
                "verification_status": "approved",
                "profile": {
                    "public_notes": "تم التحقق الميداني",
                },
            }
        },
        change_summary="نسخة اختبار ثانية",
    )

    session.add_all([first_version, second_version])
    session.flush()

    versions_response = client.get(
        f"/api/v1/registry/sites/{site.national_id}/versions"
    )
    assert versions_response.status_code == 200

    version_numbers = {
        item["version_number"]
        for item in versions_response.json()
    }
    assert first_number in version_numbers
    assert second_number in version_numbers

    detail_response = client.get(
        f"/api/v1/registry/sites/{site.national_id}/versions/{second_number}"
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["version_number"] == second_number
    assert (
        detail_response.json()["snapshot"]["site"]["name_ar"]
        == "لبدة الكبرى"
    )

    comparison_response = client.get(
        f"/api/v1/registry/sites/{site.national_id}/versions/compare",
        params={
            "from_version": first_number,
            "to_version": second_number,
        },
    )
    assert comparison_response.status_code == 200

    comparison = comparison_response.json()

    assert comparison["site_id"] == str(site.id)
    assert comparison["from_version"] == first_number
    assert comparison["to_version"] == second_number
    assert comparison["changed"] is True
    assert comparison["changed_fields"] == 3
    assert comparison["summary"] == {
        "added": 1,
        "removed": 0,
        "modified": 2,
    }

    changes = {
        item["field"]: item
        for item in comparison["changes"]
    }

    assert changes["site.name_ar"]["change_type"] == "modified"
    assert changes["site.verification_status"]["change_type"] == "modified"
    assert changes["site.profile.public_notes"]["change_type"] == "added"

    same_version_response = client.get(
        f"/api/v1/registry/sites/{site.national_id}/versions/compare",
        params={
            "from_version": first_number,
            "to_version": first_number,
        },
    )
    assert same_version_response.status_code == 200
    assert same_version_response.json()["changed"] is False
    assert same_version_response.json()["changed_fields"] == 0
    assert same_version_response.json()["changes"] == []

    missing_detail_response = client.get(
        f"/api/v1/registry/sites/{site.national_id}/versions/999999999"
    )
    assert missing_detail_response.status_code == 404

    missing_comparison_response = client.get(
        f"/api/v1/registry/sites/{site.national_id}/versions/compare",
        params={
            "from_version": first_number,
            "to_version": 999999999,
        },
    )
    assert missing_comparison_response.status_code == 404


def test_site_version_compare_query_validation(
    registry: tuple[TestClient, Session, Site],
) -> None:
    client, _, site = registry

    response = client.get(
        f"/api/v1/registry/sites/{site.national_id}/versions/compare",
        params={
            "from_version": 0,
            "to_version": 1,
        },
    )

    assert response.status_code == 422
