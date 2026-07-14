from collections.abc import Generator

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_database_engine
from app.models import AuditLog, Site, SiteGeometry, SiteRelationship
from app.services.spatial_relationship_service import (
    calculate_bearing,
    calculate_distance,
    create_manual_relationship,
    find_nearby_staging_features,
    refresh_nearby_relationships,
    reject_relationship,
    relationship_summary,
    verify_relationship,
)


@pytest.fixture
def spatial_db() -> Generator[tuple[Session, Site], None, None]:
    engine = create_database_engine(get_settings().database_url)
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, expire_on_commit=False)
    site = session.scalar(select(Site).order_by(Site.national_id))
    assert site is not None
    try:
        yield session, site
    finally:
        session.close()
        transaction.rollback()
        connection.close()
        engine.dispose()


def test_metric_distance_dwithin_and_staging_nearby(spatial_db: tuple[Session, Site]) -> None:
    session, site = spatial_db
    geometry = session.scalar(select(SiteGeometry).where(SiteGeometry.site_id == site.id))
    assert geometry is not None
    assert calculate_distance(session, geometry.geometry, geometry.geometry) == pytest.approx(0)
    assert calculate_bearing(session, geometry.geometry, geometry.geometry) == pytest.approx(0)
    results = find_nearby_staging_features(session, site.id, radius_meters=500, geometry_type="Point", limit=100)
    assert results
    assert all(item["distance_meters"] <= 500 for item in results)
    assert all(item["geometry_type"] == "Point" for item in results)


def test_relationship_validation_duplicate_review_and_summary(spatial_db: tuple[Session, Site]) -> None:
    session, site = spatial_db
    existing = set(
        session.scalars(
            select(SiteRelationship.target_staging_feature_id).where(SiteRelationship.source_site_id == site.id)
        )
    )
    candidate = next(
        item
        for item in find_nearby_staging_features(
            session, site.id, radius_meters=500, geometry_type="Point", has_name=True, limit=100
        )
        if __import__("uuid").UUID(item["target_id"]) not in existing
    )
    target_id = __import__("uuid").UUID(candidate["target_id"])
    item = create_manual_relationship(session, site.id, target_staging_feature_id=target_id, relationship_type="nearby")
    with pytest.raises(ValueError, match="موجودة"):
        create_manual_relationship(session, site.id, target_staging_feature_id=target_id, relationship_type="nearby")
    with pytest.raises(ValueError, match="بنفسه"):
        create_manual_relationship(session, site.id, target_site_id=site.id, relationship_type="nearby")
    verify_relationship(session, site.id, item.id)
    assert item.verification_status == "approved"
    reject_relationship(session, site.id, item.id)
    assert item.verification_status == "rejected"
    assert relationship_summary(session, site.id)["total"] >= 1


def test_refresh_limit_pending_unnamed_lines_excluded_and_audited(spatial_db: tuple[Session, Site]) -> None:
    session, site = spatial_db
    created = refresh_nearby_relationships(
        session, site, radius_meters=500, relationship_type="nearby", source="staging", limit=10
    )
    assert len(created) <= 10
    assert all(item.verification_status == "pending_review" for item in created)
    assert all(item.target_staging_feature_id is not None for item in created)
    assert (
        session.scalar(
            select(func.count())
            .select_from(AuditLog)
            .where(AuditLog.action == "spatial_relationships_refreshed", AuditLog.entity_id == site.id)
        )
        >= 1
    )
    assert (
        session.scalar(
            select(func.count()).select_from(SiteRelationship).where(SiteRelationship.source_site_id == site.id)
        )
        <= 10
    )
