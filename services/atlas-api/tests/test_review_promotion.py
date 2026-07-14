from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_database_engine
from app.models import AuditLog, ImportFeature, PromotionRecord, Site, SiteGeometry, VerificationRecord
from app.services.promotion_service import PromotionNotAllowedError, promote_feature
from app.services.review_service import approve_feature


@pytest.fixture
def db() -> Generator[Session, None, None]:
    engine = create_database_engine(get_settings().database_url)
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


def feature(db: Session, kind: str = "Point") -> ImportFeature:
    promoted_feature_ids = select(PromotionRecord.import_feature_id)
    item = db.scalar(
        select(ImportFeature)
        .where(
            ImportFeature.geometry_type == kind,
            ImportFeature.missing_name.is_(False),
            ImportFeature.id.not_in(promoted_feature_ids),
        )
        .order_by(ImportFeature.source_feature_id)
    )
    assert item is not None
    return item


def accept_all(db: Session, item: ImportFeature) -> None:
    for stage in ("technical", "gis", "data", "final"):
        approve_feature(db, item.id, stage, "pytest-reviewer")


def test_line_string_cannot_be_promoted(db: Session) -> None:
    item = feature(db, "LineString")
    accept_all(db, item)
    with pytest.raises(PromotionNotAllowedError):
        promote_feature(db, item.id)


def test_unnamed_feature_cannot_be_promoted(db: Session) -> None:
    item = feature(db)
    item.name_ar = None
    item.missing_name = True
    accept_all(db, item)
    with pytest.raises(PromotionNotAllowedError):
        promote_feature(db, item.id)


def test_feature_without_all_reviews_cannot_be_promoted(db: Session) -> None:
    item = feature(db)
    approve_feature(db, item.id, "technical", "pytest-reviewer")
    with pytest.raises(PromotionNotAllowedError):
        promote_feature(db, item.id)


def test_eligible_point_creates_complete_national_record(db: Session) -> None:
    item = feature(db)
    accept_all(db, item)
    site = promote_feature(db, item.id)
    db.flush()
    assert site.national_id.startswith("LSTA-OLD-TRIPOLI-")
    assert db.scalar(select(func.count()).select_from(SiteGeometry).where(SiteGeometry.site_id == site.id)) == 1
    assert db.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.entity_id == site.id)) == 1
    assert (
        db.scalar(select(func.count()).select_from(VerificationRecord).where(VerificationRecord.site_id == site.id))
        == 1
    )
    assert db.scalar(select(func.count()).select_from(PromotionRecord).where(PromotionRecord.site_id == site.id)) == 1
    with pytest.raises(PromotionNotAllowedError):
        promote_feature(db, item.id)


def test_promotion_rolls_back_fully_on_failure(db: Session) -> None:
    item = feature(db)
    accept_all(db, item)
    before = db.scalar(select(func.count()).select_from(Site))
    with pytest.raises(RuntimeError, match="forced promotion failure"):
        promote_feature(db, item.id, fail_after_site=True)
    assert db.scalar(select(func.count()).select_from(Site)) == before


def test_remaining_staging_rows_are_unchanged(db: Session) -> None:
    assert db.scalar(select(func.count()).select_from(ImportFeature)) == 430
