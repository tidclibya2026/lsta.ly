from collections.abc import Generator
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import create_database_engine
from app.services.media_review_import_service import import_review_csv
from app.services.media_review_service import (
    bulk_review_preview,
    calculate_media_review_summary,
    list_media_review_items,
    submit_media_review,
)


@pytest.fixture
def media_session() -> Generator[Session, None, None]:
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


def test_csv_import_380_and_duplicate_prevention(media_session: Session) -> None:
    path = Path(__file__).parents[3] / "reports/media/old_tripoli_image_review.csv"
    first = import_review_csv(media_session, path)
    second = import_review_csv(media_session, path)
    assert first["read"] == 380 and second["inserted"] == 0


def test_summary_filters_pagination_and_bulk_preview(media_session: Session) -> None:
    summary = calculate_media_review_summary(media_session)
    items, total = list_media_review_items(media_session, review_status="pending_review", limit=5, offset=0)
    assert summary["total"] == 380 and summary["approved_public"] == 0 and total == 380 and len(items) == 5
    preview = bulk_review_preview(media_session, [item.id for item in items])
    assert preview["matched"] == 5


def test_permission_and_public_approval_validation(media_session: Session) -> None:
    item = list_media_review_items(media_session, limit=1)[0][0]
    with pytest.raises(PermissionError):
        submit_media_review(
            media_session, item.id, {"review_status": "approved", "rights_status": "approved_internal"}, "viewer"
        )
    with pytest.raises(PermissionError):
        submit_media_review(
            media_session,
            item.id,
            {"review_status": "approved", "rights_status": "approved_public", "reviewer_notes": "أساس"},
            "reviewer",
        )
    with pytest.raises(ValueError):
        submit_media_review(
            media_session, item.id, {"review_status": "approved", "rights_status": "approved_public"}, "data_manager"
        )
    approved = submit_media_review(
        media_session,
        item.id,
        {"review_status": "approved", "rights_status": "approved_public", "rights_evidence": "تصريح موثق"},
        "data_manager",
    )
    assert approved.rights_status == "approved_public"
